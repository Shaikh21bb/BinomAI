"""Saved quick PDF checks; no project, tender, or source file is created."""

import base64
import binascii
from datetime import datetime, timedelta, timezone
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
import redis.asyncio as redis
from sqlalchemy import func, literal_column, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_user, get_db, get_redis
from app.core.config import settings
from app.core.parsers import DocumentParser
from app.core.pdf_ocr import (
    MAX_OCR_PAGES,
    PdfOcrLimitError,
    PdfOcrProcessingError,
    PdfOcrUnavailableError,
    extract_pdf_text_with_ocr,
)
from app.core.rate_limit import enforce_rate_limit
from app.db.models.quick_check_report import QuickCheckReport
from app.db.models.user import User
from app.services.market_search import search_products
from app.services.product_extraction import extract_products_from_text
from app.services.product_matching import evaluate_product_leads
from app.tasks.product_search_tasks import _build_search_query
from app.tasks.quick_check_tasks import search_quick_report_task

router = APIRouter()
_MAX_PDF_BYTES = 20 * 1024 * 1024
_MAX_PAGES = 60
_MAX_ITEMS = 20
_HISTORY_PAGE_SIZE = 20
_READY_JSONPATH = literal_column("'$[*] ? (@.state == \"ready\")'::jsonpath")
_ACTIVE_RUN_WINDOW = timedelta(minutes=10)


class QuickSearchRequest(BaseModel):
    product_name: str = Field(min_length=3, max_length=500)
    specs: str | None = Field(default=None, max_length=12000)
    report_id: uuid.UUID | None = None
    item_index: int | None = Field(default=None, ge=0, lt=_MAX_ITEMS)


def _report_payload(report: QuickCheckReport) -> dict:
    return {
        "id": str(report.id),
        "filename": report.filename,
        "page_count": report.page_count,
        "ocr_pages": report.ocr_pages,
        "total_items": report.total_items,
        "truncated": report.truncated,
        "items": report.items,
        "processing_state": report.processing_state,
        "created_at": report.created_at,
        "updated_at": report.updated_at,
    }


def _encode_cursor(created_at: datetime, report_id: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{report_id}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode("utf-8")
        created_at_raw, report_id_raw = raw.rsplit("|", 1)
        created_at = datetime.fromisoformat(created_at_raw)
        if created_at.tzinfo is None:
            raise ValueError("Cursor timestamp needs a timezone")
        return created_at, uuid.UUID(report_id_raw)
    except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
        raise HTTPException(status_code=422, detail="Некорректный указатель страницы истории.") from exc


async def _report_or_404(
    db: AsyncSession, report_id: uuid.UUID, user: User, *, lock: bool = False,
) -> QuickCheckReport:
    query = select(QuickCheckReport).where(
        QuickCheckReport.id == report_id,
        QuickCheckReport.company_id == user.company_id,
        QuickCheckReport.created_by == user.id,
    )
    if lock:
        query = query.with_for_update()
    report = (await db.execute(query)).scalars().first()
    if report is None:
        raise HTTPException(status_code=404, detail="Проверка не найдена.")
    return report


@router.get("/reports")
async def list_quick_reports(
    cursor: str | None = Query(default=None, max_length=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cursor_pair = _decode_cursor(cursor) if cursor else None
    scope = (QuickCheckReport.company_id == user.company_id, QuickCheckReport.created_by == user.id)
    checked_count = func.jsonb_array_length(
        func.jsonb_path_query_array(QuickCheckReport.items, _READY_JSONPATH)
    )
    totals = (await db.execute(
        select(
            func.count(QuickCheckReport.id),
            func.coalesce(func.sum(QuickCheckReport.total_items), 0),
            func.coalesce(func.sum(checked_count), 0),
        ).where(*scope)
    )).one()
    query = select(
        QuickCheckReport.id,
        QuickCheckReport.filename,
        QuickCheckReport.created_at,
        QuickCheckReport.total_items,
        QuickCheckReport.processing_state,
        checked_count.label("checked_items"),
    ).where(*scope)
    if cursor_pair:
        query = query.where(tuple_(QuickCheckReport.created_at, QuickCheckReport.id) < tuple_(*cursor_pair))
    query = query.order_by(QuickCheckReport.created_at.desc(), QuickCheckReport.id.desc()).limit(_HISTORY_PAGE_SIZE + 1)
    rows = (await db.execute(query)).mappings().all()
    reports = rows[:_HISTORY_PAGE_SIZE]
    return {"reports": [
        {
            "id": str(report["id"]),
            "filename": report["filename"],
            "created_at": report["created_at"],
            "total_items": report["total_items"],
            "checked_items": report["checked_items"],
            "processing_state": report["processing_state"],
        }
        for report in reports
    ], "stats": {
        "total_reports": totals[0],
        "total_items": totals[1],
        "checked_items": totals[2],
    }, "next_cursor": _encode_cursor(reports[-1]["created_at"], reports[-1]["id"])
        if len(rows) > _HISTORY_PAGE_SIZE else None}


@router.get("/reports/{report_id}")
async def get_quick_report(
    report_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return _report_payload(await _report_or_404(db, report_id, user))


@router.post("/reports/{report_id}/run")
async def run_quick_report(
    report_id: uuid.UUID,
    user: User = Depends(get_current_user),
    cache: redis.Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
):
    """Resume an interrupted report without re-uploading the PDF."""
    await enforce_rate_limit(
        cache, scope="quick-check-run", subject=str(user.id), rate=settings.RATE_LIMIT_AI_OPS,
    )
    report = await _report_or_404(db, report_id, user, lock=True)
    if report.processing_state in {"queued", "running"} and report.updated_at and (
        datetime.now(timezone.utc) - report.updated_at < _ACTIVE_RUN_WINDOW
    ):
        return _report_payload(report)
    if all(item.get("state") == "ready" for item in report.items):
        report.processing_state = "completed"
        await db.commit()
        return _report_payload(report)
    report.run_id = uuid.uuid4()
    report.processing_state = "queued"
    await db.commit()
    try:
        search_quick_report_task.delay(str(report.id), str(report.run_id))
    except Exception:
        report.processing_state = "error"
        await db.commit()
    return _report_payload(report)


@router.delete("/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quick_report(
    report_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete one saved result owned by the signed-in user."""
    report = await _report_or_404(db, report_id, user, lock=True)
    await db.delete(report)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/parse")
async def parse_quick_pdf(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    cache: redis.Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
):
    """Extract positions and save the result, without storing the source PDF."""
    await enforce_rate_limit(
        cache,
        scope="quick-check-upload",
        subject=str(user.id),
        rate=settings.RATE_LIMIT_UPLOADS,
    )
    if not (file.filename or "").lower().endswith(".pdf") or file.content_type not in {
        "application/pdf", "application/octet-stream",
    }:
        raise HTTPException(status_code=415, detail="Загрузите PDF-файл технической спецификации.")
    contents = await file.read(_MAX_PDF_BYTES + 1)
    if len(contents) > _MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="PDF для быстрой проверки не должен превышать 20 МБ.")
    if not contents.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="Файл не является корректным PDF.")

    pages = await run_in_threadpool(DocumentParser.get_page_count, contents, "application/pdf")
    if pages is None:
        raise HTTPException(status_code=422, detail="Не удалось прочитать PDF.")
    if pages > _MAX_PAGES:
        raise HTTPException(status_code=413, detail="Для быстрой проверки загрузите PDF не более 60 страниц.")
    try:
        raw_text, ocr_pages = await run_in_threadpool(extract_pdf_text_with_ocr, contents)
    except PdfOcrLimitError:
        raise HTTPException(status_code=413, detail=f"Для быстрой проверки скана загрузите не более {MAX_OCR_PAGES} отсканированных страниц.")
    except PdfOcrUnavailableError:
        raise HTTPException(status_code=503, detail="Распознавание сканов пока недоступно на сервере. Повторите позже или загрузите PDF с текстовым слоем.")
    except PdfOcrProcessingError:
        raise HTTPException(status_code=422, detail="Не удалось распознать страницы PDF. Проверьте качество скана или попробуйте PDF с текстовым слоем.")
    except ValueError:
        raise HTTPException(status_code=422, detail="Не удалось извлечь текст из PDF.")
    cleaned = DocumentParser.clean_text(raw_text)
    if not cleaned:
        raise HTTPException(status_code=422, detail="Текст не найден даже после распознавания. Проверьте качество скана.")
    products = extract_products_from_text(cleaned)
    if not products:
        raise HTTPException(status_code=422, detail="В PDF не найдены позиции товаров. Проверьте, что это техническая спецификация.")
    report = QuickCheckReport(
        id=uuid.uuid4(),
        company_id=user.company_id,
        created_by=user.id,
        filename=(file.filename or "specification.pdf")[:500],
        page_count=pages,
        ocr_pages=ocr_pages,
        total_items=len(products),
        truncated=len(products) > _MAX_ITEMS,
        items=[{**item, "state": "pending", "results": [], "checked_at": None}
               for item in jsonable_encoder(products[:_MAX_ITEMS])],
        processing_state="queued",
        run_id=uuid.uuid4(),
    )
    db.add(report)
    await db.commit()
    try:
        search_quick_report_task.delay(str(report.id), str(report.run_id))
    except Exception:
        report.processing_state = "error"
        await db.commit()
    return _report_payload(report)


@router.post("/search")
async def search_quick_product(
    body: QuickSearchRequest,
    user: User = Depends(get_current_user),
    cache: redis.Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
):
    """Find concrete public product pages and verify their published specs."""
    await enforce_rate_limit(
        cache,
        scope="quick-check-search",
        subject=str(user.id),
        rate=settings.RATE_LIMIT_AI_OPS,
    )
    if (body.report_id is None) != (body.item_index is None):
        raise HTTPException(status_code=422, detail="Укажите номер сохранённой проверки и позиции вместе.")
    name, specs = body.product_name, body.specs
    if body.report_id is not None and body.item_index is not None:
        report = await _report_or_404(db, body.report_id, user)
        if report.processing_state in {"queued", "running"}:
            raise HTTPException(status_code=409, detail="Эта проверка уже выполняется в фоне.")
        if body.item_index >= len(report.items):
            raise HTTPException(status_code=404, detail="Позиция не найдена.")
        item = report.items[body.item_index]
        if item.get("product_name") != body.product_name:
            raise HTTPException(status_code=409, detail="Позиция изменилась. Откройте сохранённую проверку снова.")
        name, specs = item["product_name"], item.get("specs")

    query = _build_search_query(name, specs)
    results = await search_products(query)
    checked = jsonable_encoder((await evaluate_product_leads(name, specs, results))[:16])
    checked_at = datetime.now(timezone.utc).isoformat()

    if body.report_id is not None and body.item_index is not None:
        report = await _report_or_404(db, body.report_id, user, lock=True)
        updated = list(report.items)
        updated[body.item_index] = {
            **updated[body.item_index],
            "state": "ready",
            "results": checked,
            "checked_at": checked_at,
        }
        report.items = updated
        if all(row.get("state") in {"ready", "error"} for row in updated):
            report.processing_state = "completed"
        await db.flush()

    return {"results": checked, "checked_at": checked_at}
