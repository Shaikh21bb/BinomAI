import io
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.models.product_search import ProductSearchItem
from app.db.models.project import Project
from app.db.models.sourcing import SourcingPlan, SupplierOffer
from app.db.models.user import User
from app.schemas.sourcing import (
    QuoteImportResult,
    RfqDraftRequest,
    RfqDraftResponse,
    SourcingPlanUpdate,
    SupplierOfferCreate,
    SupplierOfferResponse,
    SupplierOfferUpdate,
    TenderLineItemCreate,
    TenderLineItemUpdate,
)
from app.services.sourcing import (
    build_comparison,
    build_rfq_draft,
    match_line_item,
    normalize_name,
    normalize_unit,
    parse_quote_file,
    quote_row_payload,
)


router = APIRouter()
MAX_QUOTE_FILE_BYTES = 5 * 1024 * 1024


async def _project_or_404(db: AsyncSession, project_id: uuid.UUID, user: User) -> Project:
    stmt = select(Project).where(Project.id == project_id, Project.company_id == user.company_id)
    project = (await db.execute(stmt)).scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _items(db: AsyncSession, project_id: uuid.UUID, company_id: uuid.UUID) -> list[ProductSearchItem]:
    stmt = (
        select(ProductSearchItem)
        .where(ProductSearchItem.project_id == project_id, ProductSearchItem.company_id == company_id)
        .order_by(ProductSearchItem.created_at.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def _item_or_404(
    db: AsyncSession, project_id: uuid.UUID, company_id: uuid.UUID, item_id: uuid.UUID
) -> ProductSearchItem:
    stmt = select(ProductSearchItem).where(
        ProductSearchItem.id == item_id,
        ProductSearchItem.project_id == project_id,
        ProductSearchItem.company_id == company_id,
    )
    item = (await db.execute(stmt)).scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Tender item not found")
    return item


async def _offer_or_404(
    db: AsyncSession, project_id: uuid.UUID, company_id: uuid.UUID, offer_id: uuid.UUID
) -> SupplierOffer:
    stmt = select(SupplierOffer).where(
        SupplierOffer.id == offer_id,
        SupplierOffer.project_id == project_id,
        SupplierOffer.company_id == company_id,
    )
    offer = (await db.execute(stmt)).scalars().first()
    if not offer:
        raise HTTPException(status_code=404, detail="Supplier offer not found")
    return offer


@router.get("/{project_id}/sourcing")
async def get_sourcing_comparison(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await _project_or_404(db, project_id, current_user)
    items = await _items(db, project_id, current_user.company_id)
    offer_stmt = (
        select(SupplierOffer)
        .where(SupplierOffer.project_id == project_id, SupplierOffer.company_id == current_user.company_id)
        .order_by(SupplierOffer.created_at.desc())
    )
    offers = list((await db.execute(offer_stmt)).scalars().all())
    plan_stmt = select(SourcingPlan).where(
        SourcingPlan.project_id == project_id, SourcingPlan.company_id == current_user.company_id
    )
    plan = (await db.execute(plan_stmt)).scalars().first()
    margin = plan.target_margin_pct if plan else Decimal("15")
    return build_comparison(project, items, offers, margin)


@router.patch("/{project_id}/sourcing/settings")
async def update_sourcing_settings(
    project_id: uuid.UUID,
    payload: SourcingPlanUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _project_or_404(db, project_id, current_user)
    stmt = select(SourcingPlan).where(
        SourcingPlan.project_id == project_id, SourcingPlan.company_id == current_user.company_id
    )
    plan = (await db.execute(stmt)).scalars().first()
    if plan:
        plan.target_margin_pct = payload.target_margin_pct
    else:
        plan = SourcingPlan(
            project_id=project_id,
            company_id=current_user.company_id,
            target_margin_pct=payload.target_margin_pct,
        )
        db.add(plan)
        await db.flush()
    return {"target_margin_pct": plan.target_margin_pct, "base_currency": plan.base_currency}


@router.post("/{project_id}/sourcing/items", status_code=201)
async def create_tender_line_item(
    project_id: uuid.UUID,
    payload: TenderLineItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _project_or_404(db, project_id, current_user)
    item = ProductSearchItem(
        project_id=project_id,
        company_id=current_user.company_id,
        product_name=payload.product_name,
        specs=payload.specs,
        unit=payload.unit,
        quantity=float(payload.quantity) if payload.quantity is not None else None,
        source_section=payload.source_section,
        status="manual",
        results=[],
    )
    db.add(item)
    await db.flush()
    return {
        "id": item.id,
        "product_name": item.product_name,
        "specs": item.specs,
        "unit": item.unit,
        "quantity": item.quantity,
        "source_section": item.source_section,
        "status": item.status,
    }


@router.patch("/{project_id}/sourcing/items/{item_id}")
async def update_tender_line_item(
    project_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: TenderLineItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _project_or_404(db, project_id, current_user)
    item = await _item_or_404(db, project_id, current_user.company_id, item_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, float(value) if field == "quantity" and value is not None else value)
    return {"status": "updated", "id": item.id}


@router.post("/{project_id}/sourcing/offers", response_model=SupplierOfferResponse, status_code=201)
async def create_supplier_offer(
    project_id: uuid.UUID,
    payload: SupplierOfferCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _project_or_404(db, project_id, current_user)
    items = await _items(db, project_id, current_user.company_id)
    item = None
    match_status = "unmatched"
    confidence = Decimal("0")
    if payload.item_id:
        item = await _item_or_404(db, project_id, current_user.company_id, payload.item_id)
        match_status, confidence = "matched", Decimal("1")
    else:
        item, match_status, confidence = match_line_item(payload.original_item_name, items)

    values = payload.model_dump(exclude={"item_id"})
    offer = SupplierOffer(
        **values,
        project_id=project_id,
        company_id=current_user.company_id,
        item_id=item.id if item else None,
        created_by=current_user.id,
        normalized_item_name=normalize_name(payload.original_item_name),
        normalized_unit=normalize_unit(payload.original_unit),
        source_type="manual",
        match_status=match_status,
        match_confidence=confidence,
    )
    db.add(offer)
    await db.flush()
    return offer


@router.patch("/{project_id}/sourcing/offers/{offer_id}", response_model=SupplierOfferResponse)
async def update_supplier_offer(
    project_id: uuid.UUID,
    offer_id: uuid.UUID,
    payload: SupplierOfferUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _project_or_404(db, project_id, current_user)
    offer = await _offer_or_404(db, project_id, current_user.company_id, offer_id)
    changes = payload.model_dump(exclude_unset=True)

    vat_included = changes.get("vat_included", offer.vat_included)
    vat_rate = changes.get("vat_rate", offer.vat_rate)
    if vat_included is False and vat_rate is None:
        raise HTTPException(status_code=422, detail="vat_rate is required when VAT is not included")
    quote_date = changes.get("quote_date", offer.quote_date)
    valid_until = changes.get("valid_until", offer.valid_until)
    if valid_until and quote_date and valid_until < quote_date:
        raise HTTPException(status_code=422, detail="valid_until cannot be before quote_date")

    if "item_id" in changes:
        if changes["item_id"] is None:
            offer.item_id = None
            offer.match_status = "unmatched"
            offer.match_confidence = Decimal("0")
            offer.is_selected = False
        else:
            item = await _item_or_404(db, project_id, current_user.company_id, changes["item_id"])
            offer.item_id = item.id
            offer.match_status = "matched"
            offer.match_confidence = Decimal("1")
        changes.pop("item_id")

    if changes.get("is_selected") is True:
        if not offer.item_id:
            raise HTTPException(status_code=422, detail="Match the offer to a tender item before selecting it")
        await db.execute(
            update(SupplierOffer)
            .where(
                SupplierOffer.project_id == project_id,
                SupplierOffer.company_id == current_user.company_id,
                SupplierOffer.item_id == offer.item_id,
                SupplierOffer.id != offer.id,
            )
            .values(is_selected=False)
        )
    for field, value in changes.items():
        setattr(offer, field, value)
    if "original_item_name" in changes:
        offer.normalized_item_name = normalize_name(offer.original_item_name)
    if "original_unit" in changes:
        offer.normalized_unit = normalize_unit(offer.original_unit)
    await db.flush()
    return offer


@router.delete("/{project_id}/sourcing/offers/{offer_id}", status_code=204)
async def delete_supplier_offer(
    project_id: uuid.UUID,
    offer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _project_or_404(db, project_id, current_user)
    offer = await _offer_or_404(db, project_id, current_user.company_id, offer_id)
    await db.delete(offer)
    return Response(status_code=204)


@router.post("/{project_id}/sourcing/import", response_model=QuoteImportResult)
async def import_supplier_offers(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _project_or_404(db, project_id, current_user)
    content = await file.read(MAX_QUOTE_FILE_BYTES + 1)
    if len(content) > MAX_QUOTE_FILE_BYTES:
        raise HTTPException(status_code=413, detail="Файл котировок не должен превышать 5 МБ")
    try:
        rows = parse_quote_file(file.filename or "quotes.csv", content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    items = await _items(db, project_id, current_user.company_id)
    items_by_id = {str(item.id): item for item in items}
    counts = {"matched": 0, "needs_review": 0, "unmatched": 0}
    errors: list[str] = []
    imported = 0
    for index, row in enumerate(rows, start=2):
        try:
            data = quote_row_payload(row)
            if not data["supplier_name"] or not data["original_item_name"] or data["unit_price"] is None:
                raise ValueError("обязательны поставщик, наименование и цена")
            payload = SupplierOfferCreate(**data)
            explicit_item_id = str(row.get("item_id") or "").strip()
            explicit_item = items_by_id.get(explicit_item_id)
            if explicit_item_id and not explicit_item:
                raise ValueError("указанный item_id не найден в этом проекте")
            if explicit_item:
                item, match_status, confidence = explicit_item, "matched", Decimal("1")
            else:
                item, match_status, confidence = match_line_item(payload.original_item_name, items)
            offer = SupplierOffer(
                **payload.model_dump(exclude={"item_id"}),
                project_id=project_id,
                company_id=current_user.company_id,
                item_id=item.id if item else None,
                created_by=current_user.id,
                normalized_item_name=normalize_name(payload.original_item_name),
                normalized_unit=normalize_unit(payload.original_unit),
                source_type="xlsx" if (file.filename or "").lower().endswith(".xlsx") else "csv",
                source_filename=file.filename,
                match_status=match_status,
                match_confidence=confidence,
            )
            db.add(offer)
            imported += 1
            counts[match_status] += 1
        except (ValidationError, ValueError) as exc:
            errors.append(f"Строка {index}: {str(exc)[:240]}")
    await db.flush()
    return QuoteImportResult(imported=imported, errors=errors[:50], **counts)


@router.get("/{project_id}/sourcing/import-template")
async def download_import_template(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _project_or_404(db, project_id, current_user)
    header = (
        "supplier_name,item_name,unit,quantity,unit_price,price_quantity,currency,exchange_rate,"
        "vat_included,vat_rate,moq,available,delivery_cost,lead_time_days,warranty_months,"
        "certificates,compliance,quote_date,valid_until,notes\n"
    )
    example = (
        'ТОО Поставщик,Кабель ВВГнг,м,1000,450,1,KZT,,да,12,100,1200,25000,7,24,'
        '"СТ-KZ; сертификат соответствия",compliant,2026-09-23,2026-10-23,Соответствует ТЗ\n'
    )
    stream = io.BytesIO(("\ufeff" + header + example).encode("utf-8"))
    return StreamingResponse(
        stream,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="supplier_quotes_template.csv"'},
    )


@router.post("/{project_id}/sourcing/rfq-draft", response_model=RfqDraftResponse)
async def create_rfq_draft(
    project_id: uuid.UUID,
    payload: RfqDraftRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await _project_or_404(db, project_id, current_user)
    items = await _items(db, project_id, current_user.company_id)
    if payload.item_ids:
        wanted = set(payload.item_ids)
        items = [item for item in items if item.id in wanted]
        if len(items) != len(wanted):
            raise HTTPException(status_code=404, detail="One or more tender items were not found")
    if not items:
        raise HTTPException(status_code=422, detail="Добавьте хотя бы одну позицию тендера")
    subject, body = build_rfq_draft(
        project,
        items,
        payload.response_deadline,
        payload.delivery_location,
        payload.notes,
    )
    return RfqDraftResponse(
        subject=subject,
        body=body,
        disclaimer="Черновик не отправлен. Проверьте реквизиты, требования и сроки перед отправкой поставщику.",
    )
