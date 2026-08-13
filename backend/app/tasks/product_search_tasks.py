import asyncio
import uuid
import structlog
from typing import List, Optional
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.db.session import async_task_session_factory as async_session_factory
from app.db.models.project import Project
from app.db.models.company import Company
from app.db.models.document import Document
from app.db.models.product_search import ProductSearchItem
from app.core.supabase import supabase_admin
from app.services.product_extraction import extract_products_from_text
from app.services.market_search import search_products

logger = structlog.get_logger(__name__)


def _region_of(company) -> Optional[str]:
    """Best-effort city/region extraction from company addresses."""
    for addr in (getattr(company, "actual_address", None), getattr(company, "legal_address", None)):
        if not addr:
            continue
        parts = [p.strip() for p in str(addr).replace("\n", ",").split(",")]
        # Kazakh addresses: ... , г. Алматы, ...  / ... , Алматы облысы, ...
        for p in parts:
            if "облыс" in p.lower():
                return p.strip()
        for p in parts:
            if p.lower().startswith(("г.", "город", "астана", "алматы", "шымкент")):
                return p.strip()
    return None


async def run_product_search_async(task, project_id_str: str) -> dict:
    project_id = uuid.UUID(project_id_str)

    async with async_session_factory() as db:
        stmt = select(Project).where(Project.id == project_id)
        proj = (await db.execute(stmt)).scalars().first()
        if not proj:
            return {"status": "error", "message": "Project not found"}

        stmt_c = select(Company).where(Company.id == proj.company_id)
        company = (await db.execute(stmt_c)).scalars().first()
        region = _region_of(company)

        # Load the latest ready document's extracted text
        stmt_doc = (
            select(Document)
            .where(
                Document.project_id == project_id,
                Document.processing_status == "ready",
            )
            .order_by(Document.version.desc(), Document.created_at.desc())
            .limit(1)
        )
        doc = (await db.execute(stmt_doc)).scalars().first()
        if not doc or not doc.extracted_text_path:
            return {"status": "error", "message": "No ready document with extracted text"}

        async with supabase_admin.get_client() as client:
            resp = await client.get(f"/storage/v1/object/extracted-texts/{doc.extracted_text_path}")
            if resp.status_code != 200:
                return {"status": "error", "message": f"Failed to load extracted text: {resp.status_code}"}
            text_content = resp.text

        # Extract products from spec text
        products = extract_products_from_text(text_content)
        if not products:
            return {"status": "error", "message": "No products found in the document"}

        task.update_state(state="PROGRESS", meta={"step": f"Found {len(products)} products"})

        # Clear previous search items for this project (re-search replaces results)
        await db.execute(delete(ProductSearchItem).where(ProductSearchItem.project_id == project_id))
        await db.commit()

        stored = []
        for item in products:
            ps = ProductSearchItem(
                project_id=project_id,
                company_id=proj.company_id,
                product_name=item["product_name"],
                specs=item.get("specs"),
                unit=item.get("unit"),
                quantity=item.get("quantity"),
                source_section=item.get("source_section"),
                status="searching",
                search_region=region,
            )
            db.add(ps)
            await db.flush()
            stored.append(ps)

        await db.commit()

        # Search each product (sequential to be gentle on external services)
        for ps in stored:
            try:
                query = ps.product_name
                if ps.specs:
                    query = f"{ps.product_name} {ps.specs}"
                results = await search_products(query, region)
                ps.results = results
                ps.status = "ready"
                ps.best_match = _pick_best(results)
                logger.info("product_search_done", product_id=str(ps.id), matches=len(results))
            except Exception as e:
                logger.error("product_search_failed", product_id=str(ps.id), error=str(e))
                ps.status = "error"
                ps.error_message = str(e)[:500]
            await db.commit()

        return {"status": "success", "products_found": len(stored)}


def _pick_best(results: List[dict]) -> Optional[dict]:
    """Prefer a match with a price, then a real product image, then a known shop."""
    if not results:
        return None
    with_price = [r for r in results if r.get("price")]
    if with_price:
        with_price.sort(key=lambda r: r["price"] or 0)
        return with_price[0]
    # Prefer results with a real product photo over a favicon fallback
    def is_real_photo(r: dict) -> bool:
        img = r.get("image_url") or ""
        return bool(img) and "google.com/s2/favicons" not in img
    with_photo = [r for r in results if is_real_photo(r)]
    if with_photo:
        return with_photo[0]
    known_shops = [r for r in results if r.get("shop") and "маркетплейс" not in (r.get("title") or "")]
    return known_shops[0] if known_shops else results[0]


@shared_task(bind=True, max_retries=1, default_retry_delay=60)
def search_products_task(self, project_id_str: str):
    """Celery task wrapper for market product search."""
    logger.info("product_search_task_started", task_id=self.request.id, project_id=project_id_str)
    try:
        result = asyncio.run(run_product_search_async(self, project_id_str))
        return result
    except Exception as exc:
        logger.warning("product_search_retrying", exc=str(exc))
        raise self.retry(exc=exc)
