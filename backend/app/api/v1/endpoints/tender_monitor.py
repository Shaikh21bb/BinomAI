import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from app.api.deps import get_db, get_current_user
from app.db.models.user import User
from app.db.models.tender_lot import TenderLot
from app.schemas.tender_lot import TenderLotCreate, TenderLotOut, TenderLotListResponse
from app.services.tender_monitor import fetch_lot_page, TenderParseError
from app.core.config import settings

router = APIRouter()
logger = structlog.get_logger(__name__)

REFRESH_INTERVAL = timedelta(hours=6)


async def _refresh_lot(db: AsyncSession, lot: TenderLot, save: bool = True) -> None:
    """Re-fetch a lot page and update fields. Never raises for parse errors."""
    lot.last_check_at = datetime.utcnow()
    try:
        data = fetch_lot_page(lot.source_url)
        new_status = str(data.get("status") or "").strip() or None
        if new_status and new_status != lot.status:
            lot.prev_status = lot.status
            lot.status = new_status
            lot.status_changed_at = datetime.utcnow()
        lot.lot_number = str(data.get("lot_number") or "").strip() or lot.lot_number
        lot.name = str(data.get("name") or "").strip() or lot.name
        lot.description = str(data.get("description") or "").strip() or lot.description
        lot.customer_name = str(data.get("customer_name") or "").strip() or lot.customer_name
        lot.customer_bin = str(data.get("customer_bin") or "").strip() or lot.customer_bin
        lot.amount = data.get("amount") or lot.amount
        lot.start_date = data.get("start_date") or lot.start_date
        lot.deadline_at = data.get("deadline_at") or lot.deadline_at
        lot.last_error = None
        lot.next_check_at = datetime.utcnow() + REFRESH_INTERVAL
    except TenderParseError as e:
        lot.last_error = str(e)
        lot.next_check_at = datetime.utcnow() + timedelta(hours=1)
        logger.warning("tender_lot_refresh_failed", lot_id=str(lot.id), error=str(e))
    if save:
        await db.commit()


def _ensure_company(lot: TenderLot, user: User) -> None:
    if lot.company_id != user.company_id:
        raise HTTPException(status_code=404, detail="Лот не найден")


@router.post("/monitor", response_model=TenderLotOut, status_code=status.HTTP_201_CREATED)
async def add_monitor_lot(
    data: TenderLotCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start tracking a lot by its public page URL."""
    url = data.url.strip()
    try:
        parsed = fetch_lot_page(url)
    except TenderParseError as e:
        raise HTTPException(status_code=422, detail=str(e))

    stmt = select(TenderLot).where(
        TenderLot.company_id == current_user.company_id,
        TenderLot.source_url == url,
    )
    existing = (await db.execute(stmt)).scalars().first()
    if existing:
        raise HTTPException(status_code=409, detail="Этот лот уже в мониторинге")

    lot = TenderLot(
        company_id=current_user.company_id,
        source_url=url,
        source_host=str(parsed.get("source_host")),
        lot_number=str(parsed.get("lot_number") or "").strip() or None,
        name=str(parsed.get("name") or "").strip() or None,
        description=str(parsed.get("description") or "").strip() or None,
        customer_name=str(parsed.get("customer_name") or "").strip() or None,
        customer_bin=str(parsed.get("customer_bin") or "").strip() or None,
        amount=parsed.get("amount"),
        status=str(parsed.get("status") or "").strip() or None,
        start_date=parsed.get("start_date"),
        deadline_at=parsed.get("deadline_at"),
        last_check_at=datetime.utcnow(),
        next_check_at=datetime.utcnow() + REFRESH_INTERVAL,
    )
    db.add(lot)
    await db.commit()
    await db.refresh(lot)
    logger.info("tender_lot_added", lot_id=str(lot.id), company_id=str(current_user.company_id))
    return lot


@router.get("/monitor", response_model=TenderLotListResponse)
async def list_monitor_lots(
    q: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(TenderLot).where(TenderLot.company_id == current_user.company_id)
    if status_filter:
        stmt = stmt.where(TenderLot.status == status_filter)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            TenderLot.name.ilike(like)
            | TenderLot.lot_number.ilike(like)
            | TenderLot.customer_name.ilike(like)
        )
    total = len((await db.execute(stmt)).scalars().all())
    stmt = stmt.order_by(TenderLot.deadline_at.asc().nulls_last(), TenderLot.created_at.desc())
    items = (await db.execute(stmt)).scalars().all()
    return TenderLotListResponse(items=items, total=total)


@router.get("/monitor/{lot_id}", response_model=TenderLotOut)
async def get_monitor_lot(
    lot_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lot = (await db.execute(select(TenderLot).where(TenderLot.id == lot_id))).scalars().first()
    if not lot:
        raise HTTPException(status_code=404, detail="Лот не найден")
    _ensure_company(lot, current_user)
    return lot


@router.post("/monitor/{lot_id}/refresh", response_model=TenderLotOut)
async def refresh_monitor_lot(
    lot_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lot = (await db.execute(select(TenderLot).where(TenderLot.id == lot_id))).scalars().first()
    if not lot:
        raise HTTPException(status_code=404, detail="Лот не найден")
    _ensure_company(lot, current_user)
    await _refresh_lot(db, lot, save=True)
    await db.refresh(lot)
    return lot


@router.delete("/monitor/{lot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_monitor_lot(
    lot_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lot = (await db.execute(select(TenderLot).where(TenderLot.id == lot_id))).scalars().first()
    if not lot:
        raise HTTPException(status_code=404, detail="Лот не найден")
    _ensure_company(lot, current_user)
    await db.delete(lot)
    await db.commit()
