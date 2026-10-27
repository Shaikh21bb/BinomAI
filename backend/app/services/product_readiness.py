"""Conservative order-level evidence, separate from product-type similarity.

Search intent and a seller's claims are not verification of wholesale terms,
inventory, a selected variant, or certificate authenticity.
"""

import math
import re
from decimal import Decimal
from typing import Any

from app.services.product_pages import _IMAGE_NOISE, is_public_url

_CERTIFICATE = re.compile(r"ГОСТ|\bСТ\s*РК\b|сертифик|сертифиц|декларац|регистрационн\S*\s+удостоверен|certificat|declaration\s+of\s+conformity", re.I)


def _number(value: Any, *, zero: bool = False) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        return None
    try:
        number = float(str(value).strip().replace(",", "."))
        return number if math.isfinite(number) and (number >= 0 if zero else number > 0) else None
    except (ValueError, OverflowError):
        return None


def _unit(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    value = re.sub(r"[.\s]", "", raw.casefold())
    for kind, pattern in (
        ("piece", r"шт|штука|штуки|штук|дана|h87|pce|pcs|piece|pieces"),
        ("pack", r"упак|упаковка|упаковки|упаковок|pack|packs|pkg"),
        ("set", r"компл|комплект|комплекта|комплекты|комплектов|набор|набора|наборы|наборов|set|sets"),
        ("kg", r"кг|килограмм|килограмма|килограммы|килограммов|kg|kgm"),
        ("g", r"г|гр|грамм|грамма|граммы|граммов|g|grm"),
        ("tonne", r"т|тонна|тонны|тонн|tonne|tne"),
        ("l", r"л|литр|литра|литры|литров|l|ltr"),
        ("ml", r"мл|миллилитр|миллилитра|миллилитры|миллилитров|ml|mlt"),
        ("m", r"м|метр|метра|метры|метров|m|mtr"),
        ("mm", r"мм|миллиметр|миллиметра|миллиметры|миллиметров|mm|mmt"),
        ("cm", r"см|сантиметр|сантиметра|сантиметры|сантиметров|cm|cmt"),
        ("m2", r"м2|м²|квм|m2|m²|mtk"),
        ("m3", r"м3|м³|кубм|m3|m³|mtq"),
    ):
        if re.fullmatch(pattern, value):
            return kind
    # Generic "units" do not establish pieces, packages, kilograms or metres.
    return None


def assess_order_quantity(row: dict, quantity: Any, unit: Any) -> dict:
    requested = _number(quantity)
    stock = _number(row.get("stock_quantity"), zero=True)
    requested_kind, stock_kind = _unit(unit), _unit(row.get("stock_unit"))
    result = {
        "status": "unknown", "requested_quantity": requested,
        "requested_unit": unit if isinstance(unit, str) else None,
        "stock_quantity": stock, "stock_unit": row.get("stock_unit"),
        "reason": "Количество заказа или опубликованный остаток не подтверждены.",
    }
    if requested is None or requested_kind is None:
        result["reason"] = "Уточните количество и единицу заказа из ТЗ."
        return result
    if not row.get("page_verified") or stock is None:
        return result
    if stock_kind != requested_kind:
        result["reason"] = "Единица остатка не подтверждена или отличается от единицы заказа; пересчёт не выполнен."
        return result
    if stock < requested:
        result.update(status="shortage", missing=requested - stock, reason="Опубликованного остатка недостаточно для заказа.")
        return result
    if row.get("availability") != "InStock":
        result["reason"] = "Опубликованный остаток не подтверждён статусом наличия."
        return result
    minimum = _number(row.get("min_order_quantity"))
    if minimum is None or _unit(row.get("min_order_unit")) != requested_kind:
        result["reason"] = "Минимальная партия и её единица не опубликованы или не сопоставимы с заказом."
        return result
    if minimum > requested:
        result.update(status="shortage", reason="Заказ меньше опубликованной минимальной партии.")
        return result
    result.update(status="enough", reason="Численный остаток и минимальная партия совместимы с количеством заказа.")
    return result


def _certificate_requirements(requirements: list[dict]) -> list[str]:
    return [text for req in requirements if isinstance(req, dict)
            and isinstance(text := req.get("text", req.get("requirement")), str)
            and _CERTIFICATE.search(text)]


def has_required_certificate_evidence(row: dict, requirements: list[dict]) -> bool:
    """This discovery flow does not independently authenticate certificates.

    Never accept an injected status or a bare document link as verification.
    Registry/document identity and validity need a separate review workflow.
    """
    return not _certificate_requirements(requirements)


def _order_readiness(row: dict, quantity: Any, unit: Any) -> dict:
    gaps: list[dict[str, str]] = []
    def gap(code: str, label: str) -> None:
        gaps.append({"code": code, "label": label})

    checks = row.get("checks") or []
    type_check = next((check for check in checks if check.get("id") == "type"), checks[0] if checks else {})
    technical = [check for check in checks if check is not type_check]
    if not row.get("is_product_page") or not row.get("page_verified") or not is_public_url(row.get("url") or ""):
        gap("page", "Конкретная товарная страница не подтверждена.")
    if type_check.get("status") != "matched" or not technical or any(check.get("status") != "matched" for check in checks):
        gap("requirements", "Не все выделенные требования ТЗ подтверждены.")
    if row.get("variant_status") not in {"single", "selected"}:
        gap("variant", "Не подтверждён точный вариант товара: размер, комплектация или артикул.")
    quantity_check = assess_order_quantity(row, quantity, unit)
    if quantity_check["status"] != "enough":
        gap("quantity", quantity_check["reason"])
    image = row.get("image_url")
    if not isinstance(image, str) or not is_public_url(image) or _IMAGE_NOISE.search(image):
        gap("photo", "Фото конкретного товара не опубликовано.")
    if _number(row.get("price")) is None or not isinstance(row.get("currency"), str) or not row["currency"].strip():
        gap("price", "Цена с валютой не опубликована.")
    if (row.get("price_basis_status") != "published" or _number(row.get("price_quantity")) is None
            or _unit(row.get("price_unit")) is None or _unit(row.get("price_unit")) != _unit(unit)):
        gap("price-basis", "Не подтверждено, за какое количество и единицу указана цена.")
    elif _number(quantity) is not None and _number(row.get("price_quantity")) > _number(quantity):
        gap("price-basis", "Опубликованная цена относится к партии больше вашего заказа.")
    terms = row.get("wholesale_terms")
    if not isinstance(terms, str) or not terms.strip():
        gap("wholesale", "Оптовые условия для этого товара не опубликованы.")
    phones = row.get("seller_phones") if isinstance(row.get("seller_phones"), list) else []
    if not any(isinstance(value, str) and 7 <= len(re.sub(r"\D", "", value)) <= 15
               for value in [*phones, row.get("seller_phone")]):
        gap("phone", "Публичный телефон продавца не подтверждён.")
    if not has_required_certificate_evidence(row, checks):
        gap("certificate", "Документ по ГОСТ/сертификату из ТЗ требует проверки: принадлежность товару и срок действия не подтверждены.")
    mismatch = any(check.get("status") == "mismatch" for check in checks)
    unavailable = row.get("availability") in {"OutOfStock", "SoldOut", "Discontinued"}
    status = "not_suitable" if mismatch or unavailable or quantity_check["status"] == "shortage" else "needs_confirmation" if gaps else "ready"
    return {"status": status, "gaps": gaps, "quantity": quantity_check}


def annotate_order_readiness(results: list[dict], quantity: Any, unit: Any) -> list[dict]:
    """Attach current-order evidence; never reuse a source-provided readiness flag."""
    for row in results:
        checks = row.get("checks") or []
        changed = False
        for check in checks:
            if _CERTIFICATE.search(check.get("requirement") or "") and check.get("status") == "matched":
                check.update(status="unknown", reason="На странице есть заявление, но подтверждающий документ не проверен.")
                changed = True
        if changed and row.get("match_status") != "mismatch":
            row["match_status"] = "partial" if any(check.get("status") == "matched" for check in checks) else "unknown"
        row["order_readiness"] = _order_readiness(row, quantity, unit)
    return results
