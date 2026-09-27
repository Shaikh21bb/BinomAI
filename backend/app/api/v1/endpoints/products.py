import csv
import io
from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.db.models.product_search import ProductSearchItem
from app.db.models.project import Project
from app.db.models.supplier_offer import SupplierOffer, SourcingSettings
from app.db.models.user import User
from app.schemas.product_search import (
    ProductSearchItemCreate,
    ProductSearchItemResponse,
    ProductSearchItemUpdate,
)
from app.schemas.supplier_offer import (
    OfferSelectionRequest,
    RFQDraftRequest,
    SourcingSettingsUpdate,
    SupplierOfferCreate,
    SupplierOfferResponse,
    SupplierOfferUpdate,
)
from app.services.supplier_comparison import (
    build_rfq_draft,
    compare_offers,
    match_tender_item,
    normalize_currency,
    normalize_name,
    normalize_unit,
)
from app.services.sourcing_csv import build_sourcing_export, build_supplier_import_template
from app.tasks.product_search_tasks import search_products_task

router = APIRouter()


async def _get_project_or_404(db: AsyncSession, project_id: uuid.UUID, user: User) -> Project:
    stmt = select(Project).where(Project.id == project_id, Project.company_id == user.company_id)
    project = (await db.execute(stmt)).scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _get_item_or_404(
    db: AsyncSession, project_id: uuid.UUID, item_id: uuid.UUID, user: User
) -> ProductSearchItem:
    stmt = select(ProductSearchItem).where(
        ProductSearchItem.id == item_id,
        ProductSearchItem.project_id == project_id,
        ProductSearchItem.company_id == user.company_id,
    )
    item = (await db.execute(stmt)).scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Tender item not found")
    return item


async def _get_offer_or_404(
    db: AsyncSession, project_id: uuid.UUID, offer_id: uuid.UUID, user: User
) -> SupplierOffer:
    stmt = select(SupplierOffer).where(
        SupplierOffer.id == offer_id,
        SupplierOffer.project_id == project_id,
        SupplierOffer.company_id == user.company_id,
    )
    offer = (await db.execute(stmt)).scalars().first()
    if not offer:
        raise HTTPException(status_code=404, detail="Supplier offer not found")
    return offer


def _offer_response(offer: SupplierOffer) -> dict[str, Any]:
    return SupplierOfferResponse.model_validate(offer).model_dump(mode="json")


@router.post("/{project_id}/products/search", status_code=202)
async def start_product_search(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Extract tender items and discover supplier leads in the background."""
    await _get_project_or_404(db, project_id, current_user)
    search_products_task.delay(str(project_id))
    return {
        "status": "started",
        "message": "Извлечение позиций и поиск потенциальных поставщиков запущены",
    }


@router.get("/{project_id}/products", response_model=List[ProductSearchItemResponse])
async def list_product_search_items(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_project_or_404(db, project_id, current_user)
    stmt = (
        select(ProductSearchItem)
        .where(
            ProductSearchItem.project_id == project_id,
            ProductSearchItem.company_id == current_user.company_id,
            ProductSearchItem.is_active.is_(True),
        )
        .order_by(ProductSearchItem.created_at.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


@router.post("/{project_id}/products", response_model=ProductSearchItemResponse, status_code=201)
async def create_product_item(
    project_id: uuid.UUID,
    payload: ProductSearchItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_project_or_404(db, project_id, current_user)
    item = ProductSearchItem(
        project_id=project_id,
        company_id=current_user.company_id,
        **payload.model_dump(),
        normalized_name=normalize_name(payload.product_name),
        normalized_unit=normalize_unit(payload.unit),
        source_type="manual",
        status="ready",
        results=[],
        is_active=True,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


@router.patch("/{project_id}/products/{item_id}", response_model=ProductSearchItemResponse)
async def update_product_item(
    project_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: ProductSearchItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_project_or_404(db, project_id, current_user)
    item = await _get_item_or_404(db, project_id, item_id, current_user)
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(item, key, value)
    if "product_name" in values:
        item.normalized_name = normalize_name(item.product_name)
    if "unit" in values:
        item.normalized_unit = normalize_unit(item.unit)
    await db.flush()
    return item


@router.delete("/{project_id}/products/{item_id}", status_code=204)
async def archive_product_item(
    project_id: uuid.UUID,
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_project_or_404(db, project_id, current_user)
    item = await _get_item_or_404(db, project_id, item_id, current_user)
    item.is_active = False


@router.post("/{project_id}/supplier-offers", response_model=SupplierOfferResponse, status_code=201)
async def create_supplier_offer(
    project_id: uuid.UUID,
    payload: SupplierOfferCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_project_or_404(db, project_id, current_user)
    if payload.product_item_id:
        await _get_item_or_404(db, project_id, payload.product_item_id, current_user)
    values = payload.model_dump()
    currency = normalize_currency(values["currency"])
    if not currency:
        raise HTTPException(status_code=422, detail="Неподдерживаемая валюта")
    values["currency"] = currency
    offer = SupplierOffer(
        project_id=project_id,
        company_id=current_user.company_id,
        created_by=current_user.id,
        source_payload={},
        match_candidates=[],
        is_selected=False,
        **values,
    )
    db.add(offer)
    await db.flush()
    await db.refresh(offer)
    return offer


@router.patch("/{project_id}/supplier-offers/{offer_id}", response_model=SupplierOfferResponse)
async def update_supplier_offer(
    project_id: uuid.UUID,
    offer_id: uuid.UUID,
    payload: SupplierOfferUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_project_or_404(db, project_id, current_user)
    offer = await _get_offer_or_404(db, project_id, offer_id, current_user)
    values = payload.model_dump(exclude_unset=True)
    if "product_item_id" in values and values["product_item_id"]:
        await _get_item_or_404(db, project_id, values["product_item_id"], current_user)
    if "currency" in values:
        currency = normalize_currency(values["currency"])
        if not currency:
            raise HTTPException(status_code=422, detail="Неподдерживаемая валюта")
        values["currency"] = currency
    resulting_unit_price = values.get("unit_price", offer.unit_price)
    resulting_total_price = values.get("total_price", offer.total_price)
    resulting_quantity = values.get("offered_quantity", offer.offered_quantity)
    if resulting_unit_price is None and resulting_total_price is None:
        raise HTTPException(status_code=422, detail="Укажите цену за единицу или общую сумму")
    if resulting_unit_price is None and resulting_total_price is not None and resulting_quantity is None:
        raise HTTPException(status_code=422, detail="Для общей суммы укажите объём предложения")
    for key, value in values.items():
        setattr(offer, key, value)
    if values.get("product_item_id") and "match_status" not in values:
        offer.match_status = "confirmed"
    await db.flush()
    return offer


@router.delete("/{project_id}/supplier-offers/{offer_id}", status_code=204)
async def delete_supplier_offer(
    project_id: uuid.UUID,
    offer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_project_or_404(db, project_id, current_user)
    offer = await _get_offer_or_404(db, project_id, offer_id, current_user)
    await db.delete(offer)


CSV_ALIASES = {
    "item_id": {"item_id", "tender_item_id", "id_позиции", "ид_позиции"},
    "product_name": {"product_name", "товар", "наименование", "позиция"},
    "supplier_name": {"supplier_name", "supplier", "поставщик"},
    "supplier_bin": {"supplier_bin", "бин", "бин_поставщика"},
    "supplier_contact": {"supplier_contact", "контакт", "контакты"},
    "supplier_sku": {"supplier_sku", "sku", "артикул"},
    "quoted_unit": {"unit", "quoted_unit", "единица", "ед_изм"},
    "offered_quantity": {"quantity", "offered_quantity", "количество", "объем"},
    "unit_conversion_factor": {"conversion_factor", "коэффициент_пересчета"},
    "unit_price": {"unit_price", "цена", "цена_за_единицу"},
    "total_price": {"total_price", "сумма", "общая_сумма"},
    "currency": {"currency", "валюта"},
    "exchange_rate_to_kzt": {"exchange_rate_to_kzt", "курс_в_kzt", "курс_kzt"},
    "exchange_rate_date": {"exchange_rate_date", "дата_курса"},
    "vat_included": {"vat_included", "ндс_включен", "с_ндс"},
    "vat_rate": {"vat_rate", "ставка_ндс", "ндс_percent"},
    "min_order_quantity": {"min_order", "минимальный_заказ"},
    "availability_status": {"availability", "availability_status", "наличие"},
    "available_quantity": {"available_quantity", "доступное_количество"},
    "delivery_cost": {"delivery_cost", "стоимость_доставки"},
    "delivery_days": {"delivery_days", "срок_доставки_дней"},
    "warranty_months": {"warranty_months", "гарантия_месяцев"},
    "certificates": {"certificates", "сертификаты"},
    "specification_compliant": {"specification_compliant", "соответствует_тз"},
    "compliance_notes": {"compliance_notes", "комментарий_по_соответствию"},
    "quote_date": {"quote_date", "дата_предложения"},
    "price_valid_until": {"price_valid_until", "цена_действует_до"},
    "source_reference": {"source_reference", "ссылка", "источник"},
    "notes": {"notes", "примечание", "комментарий"},
}


def _header_key(value: str) -> str:
    return "_".join(value.strip().casefold().replace("ё", "е").split())


def _canonical_headers(fieldnames: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in fieldnames:
        key = _header_key(raw)
        for canonical, aliases in CSV_ALIASES.items():
            if key in aliases:
                result[raw] = canonical
                break
    return result


def _none(value: Any) -> Any:
    return None if value is None or str(value).strip() == "" else str(value).strip()


def _bool(value: Any) -> Optional[bool]:
    value = (_none(value) or "").casefold()
    if value in {"1", "true", "yes", "да", "включен", "соответствует"}:
        return True
    if value in {"0", "false", "no", "нет", "не включен", "не соответствует"}:
        return False
    return None


def _date(value: Any) -> Optional[date]:
    value = _none(value)
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Неверная дата: {value}")


def _csv_payload(row: dict[str, Any]) -> dict[str, Any]:
    numeric = {
        "offered_quantity",
        "unit_conversion_factor",
        "unit_price",
        "total_price",
        "exchange_rate_to_kzt",
        "vat_rate",
        "min_order_quantity",
        "available_quantity",
        "delivery_cost",
    }
    integer = {"delivery_days", "warranty_months"}
    payload: dict[str, Any] = {}
    for key, raw in row.items():
        value = _none(raw)
        if value is None:
            continue
        if key in numeric:
            payload[key] = Decimal(value.replace(" ", "").replace(",", "."))
        elif key in integer:
            payload[key] = int(value)
        elif key in {"vat_included", "specification_compliant"}:
            payload[key] = _bool(value)
        elif key in {"exchange_rate_date", "quote_date", "price_valid_until"}:
            payload[key] = _date(value)
        elif key == "certificates":
            payload[key] = [part.strip() for part in value.replace("|", ";").split(";") if part.strip()]
        elif key == "availability_status":
            aliases = {
                "в наличии": "available",
                "ограничено": "limited",
                "нет": "unavailable",
                "неизвестно": "unknown",
            }
            payload[key] = aliases.get(value.casefold(), value.casefold())
        else:
            payload[key] = value
    return payload


@router.post("/{project_id}/supplier-offers/import")
async def import_supplier_offers(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_project_or_404(db, project_id, current_user)
    raw = await file.read(2_000_001)
    if len(raw) > 2_000_000:
        raise HTTPException(status_code=413, detail="CSV-файл не должен превышать 2 МБ")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw.decode("cp1251")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=422, detail="CSV должен быть в UTF-8 или Windows-1251") from exc
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise HTTPException(status_code=422, detail="CSV не содержит заголовков")
    header_map = _canonical_headers(reader.fieldnames)
    if "supplier_name" not in header_map.values() or "product_name" not in header_map.values():
        raise HTTPException(status_code=422, detail="Нужны столбцы supplier_name/поставщик и product_name/наименование")

    item_stmt = select(ProductSearchItem).where(
        ProductSearchItem.project_id == project_id,
        ProductSearchItem.company_id == current_user.company_id,
        ProductSearchItem.is_active.is_(True),
    )
    items = list((await db.execute(item_stmt)).scalars().all())
    items_by_id = {str(item.id): item for item in items}
    created: list[SupplierOffer] = []
    errors: list[dict[str, Any]] = []
    for row_number, raw_row in enumerate(reader, start=2):
        mapped = {header_map[key]: value for key, value in raw_row.items() if key in header_map}
        try:
            payload = _csv_payload(mapped)
            item = None
            candidates: list[dict[str, Any]] = []
            match_status = "review"
            item_id = payload.pop("item_id", None)
            if item_id:
                item = items_by_id.get(str(item_id))
                if not item:
                    raise ValueError("item_id не относится к этому тендеру")
                match_status = "confirmed"
            else:
                item, candidates, match_status = match_tender_item(payload.get("product_name", ""), items)
            payload["product_item_id"] = item.id if item else None
            payload["match_status"] = match_status
            payload["source_type"] = "csv"
            payload.setdefault("currency", "KZT")
            validated = SupplierOfferCreate.model_validate(payload)
            values = validated.model_dump()
            currency = normalize_currency(values["currency"])
            if not currency:
                raise ValueError("неподдерживаемая валюта")
            values["currency"] = currency
            offer = SupplierOffer(
                project_id=project_id,
                company_id=current_user.company_id,
                created_by=current_user.id,
                source_payload={key: value for key, value in raw_row.items()},
                match_candidates=candidates,
                is_selected=False,
                **values,
            )
            db.add(offer)
            created.append(offer)
        except (ValueError, ValidationError, ArithmeticError) as exc:
            errors.append({"row": row_number, "message": str(exc)[:500]})
    await db.flush()
    return {
        "created": len(created),
        "needs_review": sum(offer.match_status != "confirmed" for offer in created),
        "errors": errors,
    }


@router.put("/{project_id}/sourcing/settings")
async def update_sourcing_settings(
    project_id: uuid.UUID,
    payload: SourcingSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_project_or_404(db, project_id, current_user)
    stmt = select(SourcingSettings).where(
        SourcingSettings.project_id == project_id,
        SourcingSettings.company_id == current_user.company_id,
    )
    settings = (await db.execute(stmt)).scalars().first()
    if not settings:
        settings = SourcingSettings(
            project_id=project_id,
            company_id=current_user.company_id,
            updated_by=current_user.id,
            target_margin_percent=payload.target_margin_percent,
            base_currency="KZT",
        )
        db.add(settings)
    else:
        settings.target_margin_percent = payload.target_margin_percent
        settings.updated_by = current_user.id
    await db.flush()
    return {"target_margin_percent": settings.target_margin_percent, "base_currency": "KZT"}


@router.put("/{project_id}/sourcing/items/{item_id}/selection")
async def select_supplier_offer(
    project_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: OfferSelectionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_project_or_404(db, project_id, current_user)
    await _get_item_or_404(db, project_id, item_id, current_user)
    selected = None
    if payload.offer_id:
        selected = await _get_offer_or_404(db, project_id, payload.offer_id, current_user)
        if selected.product_item_id != item_id:
            raise HTTPException(status_code=422, detail="Предложение относится к другой позиции")
    await db.execute(
        update(SupplierOffer)
        .where(
            SupplierOffer.project_id == project_id,
            SupplierOffer.company_id == current_user.company_id,
            SupplierOffer.product_item_id == item_id,
        )
        .values(is_selected=False)
    )
    if selected:
        selected.is_selected = True
    return {"selected_offer_id": str(selected.id) if selected else None}


@router.get("/{project_id}/sourcing")
async def get_sourcing_overview(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await _get_project_or_404(db, project_id, current_user)
    item_stmt = (
        select(ProductSearchItem)
        .where(
            ProductSearchItem.project_id == project_id,
            ProductSearchItem.company_id == current_user.company_id,
            ProductSearchItem.is_active.is_(True),
        )
        .order_by(ProductSearchItem.created_at.asc())
    )
    offer_stmt = select(SupplierOffer).where(
        SupplierOffer.project_id == project_id,
        SupplierOffer.company_id == current_user.company_id,
    )
    settings_stmt = select(SourcingSettings).where(
        SourcingSettings.project_id == project_id,
        SourcingSettings.company_id == current_user.company_id,
    )
    items = list((await db.execute(item_stmt)).scalars().all())
    offers = list((await db.execute(offer_stmt)).scalars().all())
    settings = (await db.execute(settings_stmt)).scalars().first()
    margin = Decimal(str(settings.target_margin_percent if settings else 15))

    active_item_ids = {item.id for item in items}
    by_item: dict[uuid.UUID, list[SupplierOffer]] = {}
    for offer in offers:
        if offer.product_item_id in active_item_ids and offer.match_status == "confirmed":
            by_item.setdefault(offer.product_item_id, []).append(offer)

    item_results = []
    total_cost = Decimal("0")
    covered = 0
    risk_count = 0
    for item in items:
        calculations = compare_offers(item, by_item.get(item.id, []), project.deadline_at)
        recommended = next((calc for calc in calculations if calc.eligible), None)
        selected = next((calc for calc in calculations if calc.offer.is_selected), None)
        effective = selected or recommended
        if effective and effective.landed_cost_kzt is not None:
            total_cost += effective.landed_cost_kzt
            covered += 1
            risk_count += len(effective.risks)
        serialized = []
        for calc in calculations:
            data = _offer_response(calc.offer)
            data["calculation"] = calc.as_dict()
            data["is_recommended"] = bool(recommended and recommended.offer.id == calc.offer.id)
            serialized.append(data)
        item_data = ProductSearchItemResponse.model_validate(item).model_dump(mode="json")
        item_data.update(
            {
                "offers": serialized,
                "recommended_offer_id": str(recommended.offer.id) if recommended else None,
                "effective_offer_id": str(effective.offer.id) if effective else None,
            }
        )
        item_results.append(item_data)

    complete = bool(items) and covered == len(items)
    estimated_bid = None
    estimated_profit = None
    if complete and margin < Decimal("100"):
        estimated_bid = total_cost / (Decimal("1") - margin / Decimal("100"))
        estimated_profit = estimated_bid - total_cost
    unmatched = [
        _offer_response(offer)
        for offer in offers
        if offer.product_item_id not in active_item_ids or offer.match_status != "confirmed"
    ]
    return {
        "settings": {"target_margin_percent": margin, "base_currency": "KZT"},
        "summary": {
            "item_count": len(items),
            "covered_item_count": covered,
            "estimated_landed_cost_kzt": total_cost if covered else None,
            "estimated_bid_kzt": estimated_bid,
            "estimated_profit_kzt": estimated_profit,
            "selected_risk_count": risk_count,
            "complete": complete,
            "disclaimer": "Расчёт является оценкой на основе введённых данных и не гарантирует фактическую цену, наличие или прибыль.",
        },
        "items": item_results,
        "unmatched_offers": unmatched,
    }


def _csv_response(content: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/{project_id}/sourcing/export.csv")
async def export_sourcing_comparison(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    overview = await get_sourcing_overview(project_id, db, current_user)
    return _csv_response(
        build_sourcing_export(overview),
        f"supplier-comparison-{project_id}.csv",
    )


@router.get("/{project_id}/supplier-offers/template.csv")
async def export_supplier_import_template(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    overview = await get_sourcing_overview(project_id, db, current_user)
    return _csv_response(
        build_supplier_import_template(overview["items"]),
        f"supplier-offers-template-{project_id}.csv",
    )


@router.post("/{project_id}/sourcing/rfq-draft")
async def create_rfq_draft(
    project_id: uuid.UUID,
    payload: RFQDraftRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await _get_project_or_404(db, project_id, current_user)
    stmt = select(ProductSearchItem).where(
        ProductSearchItem.project_id == project_id,
        ProductSearchItem.company_id == current_user.company_id,
        ProductSearchItem.is_active.is_(True),
    )
    if payload.item_ids:
        stmt = stmt.where(ProductSearchItem.id.in_(payload.item_ids))
    items = list((await db.execute(stmt)).scalars().all())
    if not items:
        raise HTTPException(status_code=422, detail="Нет позиций для запроса предложения")
    return build_rfq_draft(
        project,
        items,
        supplier_name=payload.supplier_name,
        contact_name=payload.contact_name,
        delivery_address=payload.delivery_address,
        notes=payload.notes,
    )
