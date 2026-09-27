"""Stateless PDF product check: no project or tender is created."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
import redis.asyncio as redis
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_user, get_redis
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
from app.db.models.user import User
from app.services.market_search import search_products
from app.services.product_extraction import extract_products_from_text
from app.services.product_matching import evaluate_product_leads
from app.tasks.product_search_tasks import _build_search_query

router = APIRouter()
_MAX_PDF_BYTES = 20 * 1024 * 1024
_MAX_PAGES = 60
_MAX_ITEMS = 20


class QuickSearchRequest(BaseModel):
    product_name: str = Field(min_length=3, max_length=500)
    specs: str | None = Field(default=None, max_length=12000)


@router.post("/parse")
async def parse_quick_pdf(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    cache: redis.Redis = Depends(get_redis),
):
    """Extract positions from text or scanned PDF without storing the document."""
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
    return {
        "filename": file.filename,
        "page_count": pages,
        "ocr_pages": ocr_pages,
        "total_items": len(products),
        "items": products[:_MAX_ITEMS],
        "truncated": len(products) > _MAX_ITEMS,
    }


@router.post("/search")
async def search_quick_product(
    body: QuickSearchRequest,
    user: User = Depends(get_current_user),
    cache: redis.Redis = Depends(get_redis),
):
    """Find concrete public product pages and verify their published specs."""
    await enforce_rate_limit(
        cache,
        scope="quick-check-search",
        subject=str(user.id),
        rate=settings.RATE_LIMIT_AI_OPS,
    )
    query = _build_search_query(body.product_name, body.specs)
    results = await search_products(query)
    checked = await evaluate_product_leads(body.product_name, body.specs, results)
    return {"results": checked[:16]}
