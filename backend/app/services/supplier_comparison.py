"""Deterministic supplier quote normalization, risk checks, and ranking.

This module never invents market facts. It only calculates from tender data and
supplier values supplied by a user/import/discovery lead. Unknown data remains
unknown and is surfaced as a risk.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from difflib import SequenceMatcher
from statistics import median
import re
from typing import Any, Iterable, Optional


ZERO = Decimal("0")
ONE = Decimal("1")


UNIT_DEFINITIONS: dict[str, tuple[str, Decimal]] = {
    "шт": ("piece", ONE),
    "штука": ("piece", ONE),
    "штук": ("piece", ONE),
    "pcs": ("piece", ONE),
    "pc": ("piece", ONE),
    "компл": ("set", ONE),
    "комплект": ("set", ONE),
    "set": ("set", ONE),
    "кг": ("mass", ONE),
    "kg": ("mass", ONE),
    "т": ("mass", Decimal("1000")),
    "тн": ("mass", Decimal("1000")),
    "тонна": ("mass", Decimal("1000")),
    "ton": ("mass", Decimal("1000")),
    "м": ("length", ONE),
    "пм": ("length", ONE),
    "погм": ("length", ONE),
    "погонныйм": ("length", ONE),
    "cm": ("length", Decimal("0.01")),
    "см": ("length", Decimal("0.01")),
    "мм": ("length", Decimal("0.001")),
    "mm": ("length", Decimal("0.001")),
    "м2": ("area", ONE),
    "m2": ("area", ONE),
    "м3": ("volume", ONE),
    "m3": ("volume", ONE),
    "л": ("liquid", ONE),
    "l": ("liquid", ONE),
    "литр": ("liquid", ONE),
    "мл": ("liquid", Decimal("0.001")),
    "ml": ("liquid", Decimal("0.001")),
}

CURRENCY_ALIASES = {
    "₸": "KZT",
    "ТГ": "KZT",
    "ТЕНГЕ": "KZT",
    "KZT": "KZT",
    "USD": "USD",
    "$": "USD",
    "EUR": "EUR",
    "€": "EUR",
    "RUB": "RUB",
    "РУБ": "RUB",
    "₽": "RUB",
}

BLOCKING_RISKS = {
    "unit_incompatible",
    "price_not_comparable",
    "unavailable",
    "insufficient_quantity",
    "specification_noncompliant",
    "match_unconfirmed",
    "currency_rate_missing",
    "currency_rate_stale",
    "availability_unknown",
    "certificates_missing",
    "warranty_missing",
    "deadline_risk",
    "delivery_time_unknown",
    "vat_unknown",
    "price_stale",
    "price_expires_before_tender",
    "price_freshness_unknown",
    "discovery_lead_unverified",
}


def _value(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def decimal_or_none(value: Any) -> Optional[Decimal]:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(" ", "").replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def normalize_name(value: Optional[str]) -> str:
    """Conservative name normalization for matching; source text is preserved."""
    if not value:
        return ""
    normalized = value.casefold().replace("ё", "е")
    normalized = re.sub(r"[^a-zа-я0-9]+", " ", normalized)
    return " ".join(normalized.split())


def _unit_key(value: Optional[str]) -> str:
    if not value:
        return ""
    key = value.casefold().strip().replace("²", "2").replace("³", "3")
    return re.sub(r"[\s\.]+", "", key)


def normalize_unit(value: Optional[str]) -> Optional[str]:
    definition = UNIT_DEFINITIONS.get(_unit_key(value))
    if not definition:
        return None
    dimension, factor = definition
    canonical_by_dimension = {
        "piece": "шт",
        "set": "компл",
        "mass": "кг",
        "length": "м",
        "area": "м2",
        "volume": "м3",
        "liquid": "л",
    }
    return canonical_by_dimension[dimension]


def conversion_factor(offer_unit: Optional[str], tender_unit: Optional[str]) -> Optional[Decimal]:
    """Return how many tender units are contained in one quoted unit."""
    offer = UNIT_DEFINITIONS.get(_unit_key(offer_unit))
    tender = UNIT_DEFINITIONS.get(_unit_key(tender_unit))
    if not offer or not tender or offer[0] != tender[0]:
        return None
    return offer[1] / tender[1]


def normalize_currency(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return CURRENCY_ALIASES.get(value.strip().upper())


def match_tender_item(product_name: str, items: Iterable[Any]) -> tuple[Optional[Any], list[dict[str, Any]], str]:
    """Find an exact/likely line-item match without silently accepting ambiguity."""
    needle = normalize_name(product_name)
    ranked: list[tuple[float, Any]] = []
    for item in items:
        candidate = normalize_name(_value(item, "product_name"))
        if not candidate:
            continue
        score = SequenceMatcher(None, needle, candidate).ratio()
        if needle == candidate:
            score = 1.0
        elif needle in candidate or candidate in needle:
            score = max(score, 0.88)
        ranked.append((score, item))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    candidates = [
        {
            "item_id": str(_value(item, "id")),
            "product_name": _value(item, "product_name"),
            "score": round(score, 3),
        }
        for score, item in ranked[:3]
        if score >= 0.35
    ]
    if not ranked:
        return None, candidates, "unmatched"
    top_score, top = ranked[0]
    second_score = ranked[1][0] if len(ranked) > 1 else 0.0
    if top_score >= 0.96 or (top_score >= 0.82 and top_score - second_score >= 0.12):
        return top, candidates, "confirmed"
    return None, candidates, "review"


@dataclass
class OfferCalculation:
    offer: Any
    landed_cost_kzt: Optional[Decimal]
    unit_price_kzt: Optional[Decimal]
    purchase_quantity: Optional[Decimal]
    conversion_factor: Optional[Decimal]
    risks: list[dict[str, str]]
    reasons: list[str]
    eligible: bool
    score: Decimal = ZERO

    def as_dict(self) -> dict[str, Any]:
        return {
            "landed_cost_kzt": self.landed_cost_kzt,
            "normalized_unit_price_kzt": self.unit_price_kzt,
            "purchase_quantity": self.purchase_quantity,
            "unit_conversion_factor": self.conversion_factor,
            "risks": self.risks,
            "reasons": self.reasons,
            "eligible": self.eligible,
            "score": self.score.quantize(Decimal("0.1")),
        }


def _risk(code: str, severity: str, message: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message}


def _has_certificate(required: str, supplied: Iterable[str]) -> bool:
    wanted = normalize_name(required)
    return any(
        wanted == normalize_name(value)
        or wanted in normalize_name(value)
        or normalize_name(value) in wanted
        for value in supplied
        if value
    )


def calculate_offer(
    item: Any,
    offer: Any,
    *,
    project_deadline: Optional[datetime] = None,
    today: Optional[date] = None,
) -> OfferCalculation:
    today = today or datetime.now(timezone.utc).date()
    risks: list[dict[str, str]] = []
    reasons: list[str] = []

    match_status = _value(offer, "match_status", "confirmed")
    if match_status != "confirmed":
        risks.append(_risk("match_unconfirmed", "high", "Строка предложения не подтверждена для этой позиции."))

    tender_qty = decimal_or_none(_value(item, "quantity"))
    explicit_factor = decimal_or_none(_value(offer, "unit_conversion_factor"))
    factor = explicit_factor or conversion_factor(
        _value(offer, "quoted_unit"), _value(item, "unit")
    )
    if factor is None or factor <= ZERO:
        risks.append(_risk("unit_incompatible", "high", "Единицы нельзя сопоставить без коэффициента пересчёта."))

    currency = normalize_currency(_value(offer, "currency"))
    fx = decimal_or_none(_value(offer, "exchange_rate_to_kzt"))
    if currency == "KZT":
        fx = ONE
    elif not currency or fx is None or fx <= ZERO:
        risks.append(_risk("currency_rate_missing", "high", "Для валюты не задан курс пересчёта в KZT."))
        fx = None
    else:
        fx_date = _value(offer, "exchange_rate_date")
        if not fx_date or (today - fx_date).days > 30:
            risks.append(_risk("currency_rate_stale", "medium", "Курс валюты отсутствует или старше 30 дней."))

    unit_price = decimal_or_none(_value(offer, "unit_price"))
    total_price = decimal_or_none(_value(offer, "total_price"))
    offered_qty = decimal_or_none(_value(offer, "offered_quantity"))
    if unit_price is None and total_price is not None and offered_qty and offered_qty > ZERO:
        unit_price = total_price / offered_qty
        reasons.append("Цена за единицу рассчитана из общей суммы предложения.")

    vat_included = _value(offer, "vat_included")
    vat_rate = decimal_or_none(_value(offer, "vat_rate"))
    vat_multiplier = ONE
    if vat_included is False:
        if vat_rate is None:
            risks.append(_risk("vat_unknown", "medium", "НДС не включён, но ставка не указана."))
        else:
            vat_multiplier = ONE + vat_rate / Decimal("100")
    elif vat_included is None:
        risks.append(_risk("vat_unknown", "medium", "Не указано, включён ли НДС."))

    purchase_qty = None
    goods_cost = None
    normalized_unit_price = None
    if tender_qty is not None and tender_qty > ZERO and factor and unit_price is not None and fx:
        purchase_qty = tender_qty / factor
        min_order = decimal_or_none(_value(offer, "min_order_quantity"))
        if min_order is not None and min_order > purchase_qty:
            purchase_qty = min_order
            reasons.append("Стоимость учитывает минимальный объём заказа поставщика.")
        goods_cost = purchase_qty * unit_price * vat_multiplier * fx
        normalized_unit_price = unit_price * vat_multiplier * fx / factor
    elif total_price is not None and fx and offered_qty is None:
        risks.append(_risk("price_basis_unknown", "high", "Для общей суммы не указан объём предложения."))
    else:
        risks.append(_risk("price_not_comparable", "high", "Недостаточно данных для расчёта сопоставимой стоимости."))

    delivery_cost = decimal_or_none(_value(offer, "delivery_cost"))
    if goods_cost is not None:
        goods_cost += (delivery_cost or ZERO) * (fx or ONE) * vat_multiplier

    availability = _value(offer, "availability_status", "unknown")
    if availability == "unavailable":
        risks.append(_risk("unavailable", "high", "Товар отмечен как отсутствующий."))
    elif availability == "unknown":
        risks.append(_risk("availability_unknown", "medium", "Наличие у поставщика не подтверждено."))
    available_qty = decimal_or_none(_value(offer, "available_quantity"))
    if purchase_qty is not None and available_qty is not None and available_qty < purchase_qty:
        risks.append(_risk("insufficient_quantity", "high", "Подтверждённого количества недостаточно."))

    compliant = _value(offer, "specification_compliant")
    if compliant is False:
        risks.append(_risk("specification_noncompliant", "high", "Предложение не соответствует обязательной спецификации."))
    elif compliant is None:
        risks.append(_risk("specification_unverified", "high", "Соответствие спецификации не подтверждено."))

    required_certificates = _value(item, "required_certificates", []) or []
    supplied_certificates = _value(offer, "certificates", []) or []
    missing_certificates = [
        cert for cert in required_certificates if not _has_certificate(cert, supplied_certificates)
    ]
    if missing_certificates:
        risks.append(_risk("certificates_missing", "high", "Не подтверждены сертификаты: " + ", ".join(missing_certificates)))

    if _value(item, "warranty_required", False) and not _value(offer, "warranty_months"):
        risks.append(_risk("warranty_missing", "high", "Для позиции требуется гарантия, но срок не указан."))

    deadline = _value(item, "desired_delivery_date")
    delivery_days = _value(offer, "delivery_days")
    if deadline:
        if delivery_days is None:
            risks.append(_risk("delivery_time_unknown", "medium", "Срок поставки не указан."))
        elif today + timedelta(days=delivery_days) > deadline:
            risks.append(_risk("deadline_risk", "high", "Расчётная поставка позже требуемой даты."))

    valid_until = _value(offer, "price_valid_until")
    quote_date = _value(offer, "quote_date")
    if valid_until and valid_until < today:
        risks.append(_risk("price_stale", "medium", "Срок действия цены истёк."))
    elif valid_until and project_deadline and valid_until < project_deadline.date():
        risks.append(_risk("price_expires_before_tender", "high", "Цена истекает до срока подачи тендерной заявки."))
    elif not valid_until and (not quote_date or (today - quote_date).days > 30):
        risks.append(_risk("price_freshness_unknown", "medium", "Актуальность цены не подтверждена."))

    if _value(offer, "source_type") == "discovery" and not quote_date:
        risks.append(_risk("discovery_lead_unverified", "medium", "Цена из поискового сниппета требует подтверждения поставщиком."))

    blocking = any(risk["code"] in BLOCKING_RISKS for risk in risks)
    eligible = not blocking and compliant is True and goods_cost is not None
    if compliant is True:
        reasons.append("Соответствие спецификации подтверждено.")
    if availability == "available":
        reasons.append("Наличие подтверждено.")
    if delivery_days is not None and not any(r["code"] == "deadline_risk" for r in risks):
        reasons.append("Указанный срок поставки укладывается в требуемую дату.")

    return OfferCalculation(
        offer=offer,
        landed_cost_kzt=goods_cost,
        unit_price_kzt=normalized_unit_price,
        purchase_quantity=purchase_qty,
        conversion_factor=factor,
        risks=risks,
        reasons=reasons,
        eligible=eligible,
    )


def compare_offers(item: Any, offers: Iterable[Any], project_deadline: Optional[datetime] = None) -> list[OfferCalculation]:
    calculations = [
        calculate_offer(item, offer, project_deadline=project_deadline) for offer in offers
    ]
    priced = [c.landed_cost_kzt for c in calculations if c.landed_cost_kzt is not None]
    price_median = Decimal(str(median(priced))) if len(priced) >= 3 else None
    for calc in calculations:
        if price_median and calc.landed_cost_kzt is not None and calc.landed_cost_kzt < price_median * Decimal("0.65"):
            calc.risks.append(_risk("suspiciously_cheap", "medium", "Цена более чем на 35% ниже медианы; проверьте состав и условия."))
            calc.eligible = False

    eligible_prices = [c.landed_cost_kzt for c in calculations if c.eligible and c.landed_cost_kzt is not None]
    min_price = min(eligible_prices) if eligible_prices else None

    for calc in calculations:
        score = ZERO
        if calc.eligible and min_price and calc.landed_cost_kzt:
            score += min(Decimal("40"), min_price / calc.landed_cost_kzt * Decimal("40"))
            score += Decimal("25")
            if not any(r["code"] in {"deadline_risk", "delivery_time_unknown"} for r in calc.risks):
                score += Decimal("15")
            elif not any(r["code"] == "deadline_risk" for r in calc.risks):
                score += Decimal("5")
            if not any(r["code"] in {"certificates_missing", "warranty_missing"} for r in calc.risks):
                score += Decimal("10")
            data_risks = {"vat_unknown", "price_freshness_unknown", "availability_unknown", "currency_rate_stale"}
            score += Decimal("10") - Decimal("2") * sum(r["code"] in data_risks for r in calc.risks)
            if any(r["code"] == "suspiciously_cheap" for r in calc.risks):
                score -= Decimal("10")
        calc.score = max(ZERO, min(Decimal("100"), score))

    calculations.sort(
        key=lambda c: (not c.eligible, -c.score, c.landed_cost_kzt or Decimal("Infinity"))
    )
    return calculations


def build_rfq_draft(
    project: Any,
    items: Iterable[Any],
    *,
    supplier_name: Optional[str] = None,
    contact_name: Optional[str] = None,
    delivery_address: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict[str, str]:
    project_name = _value(project, "name", "тендер")
    subject = f"Запрос коммерческого предложения — {project_name}"
    greeting = f"Здравствуйте, {contact_name}!" if contact_name else "Здравствуйте!"
    addressee = f"Для компании «{supplier_name}».\n\n" if supplier_name else ""
    lines = []
    for index, item in enumerate(items, start=1):
        qty = _value(item, "quantity")
        unit = _value(item, "unit") or "ед."
        specs = _value(item, "specs")
        line = f"{index}. {_value(item, 'product_name')} — {qty:g} {unit}" if qty is not None else f"{index}. {_value(item, 'product_name')}"
        if specs:
            line += f"; характеристики: {specs}"
        required = _value(item, "required_certificates", []) or []
        if required:
            line += f"; сертификаты: {', '.join(required)}"
        item_delivery_date = _value(item, "desired_delivery_date")
        if item_delivery_date:
            line += f"; требуемая поставка до: {item_delivery_date.isoformat()}"
        lines.append(line)
    address_text = f"\nАдрес поставки: {delivery_address}." if delivery_address else ""
    notes_text = f"\nДополнительные условия: {notes}" if notes else ""
    body = (
        f"{greeting}\n\n{addressee}Просим предоставить коммерческое предложение по следующим позициям:\n\n"
        + "\n".join(lines)
        + f"\n\nПросим отдельно указать цену за единицу и общую сумму, валюту и НДС, минимальный заказ, наличие, стоимость и срок доставки, гарантию, сертификаты, а также срок действия цены.{address_text}{notes_text}\n\n"
        "Это запрос предложения и не является заказом или обязательством заключить договор."
    )
    return {"subject": subject, "body": body}
