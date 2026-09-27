"""CSV handoff helpers for supplier sourcing.

The exporter intentionally accepts serialized dictionaries so it stays independent
from the API/ORM layer and is easy to test. Text cells are protected from spreadsheet
formula injection before they are written.
"""

import csv
import io
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable, Mapping


EXPORT_HEADERS = [
    "ID позиции",
    "Позиция ТЗ",
    "Характеристики",
    "Количество ТЗ",
    "Единица ТЗ",
    "ID предложения",
    "Поставщик",
    "БИН",
    "Товар в КП",
    "Количество в КП",
    "Единица поставщика",
    "Цена за единицу",
    "Общая сумма",
    "Валюта",
    "Курс в KZT",
    "НДС включён",
    "Ставка НДС",
    "Стоимость доставки",
    "Срок доставки, дней",
    "Наличие",
    "Доступное количество",
    "Гарантия, месяцев",
    "Сертификаты",
    "Соответствует ТЗ",
    "Дата КП",
    "Цена действует до",
    "Стоимость с доставкой, KZT",
    "Оценка",
    "Допущено к рекомендации",
    "Выбрано вручную",
    "Рекомендуется",
    "Итоговый выбор",
    "Статус сопоставления",
    "Источник",
    "Коды рисков",
    "Риски",
    "Примечание",
]

IMPORT_TEMPLATE_HEADERS = [
    "item_id",
    "Наименование",
    "Поставщик",
    "БИН",
    "Контакт",
    "Количество",
    "Единица",
    "Цена",
    "Общая сумма",
    "Валюта",
    "Курс в KZT",
    "Дата курса",
    "НДС включен",
    "Ставка НДС",
    "Минимальный заказ",
    "Наличие",
    "Доступное количество",
    "Стоимость доставки",
    "Срок доставки дней",
    "Гарантия месяцев",
    "Сертификаты",
    "Соответствует ТЗ",
    "Комментарий по соответствию",
    "Дата предложения",
    "Цена действует до",
    "Ссылка",
    "Примечание",
]


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "да" if value else "нет"
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (list, tuple, set)):
        value = "; ".join(str(part) for part in value)
    text = str(value)
    candidate = text.lstrip(" \t\r\n")
    if candidate.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def _write_csv(headers: list[str], rows: Iterable[Iterable[Any]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";", lineterminator="\r\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_cell(value) for value in row])
    return "\ufeff" + output.getvalue()


def _offer_row(
    item: Mapping[str, Any] | None,
    offer: Mapping[str, Any] | None,
    *,
    effective_offer_id: str | None = None,
) -> list[Any]:
    item = item or {}
    offer = offer or {}
    calculation = offer.get("calculation") or {}
    risks = calculation.get("risks") or []
    offer_id = str(offer.get("id") or "")
    return [
        item.get("id"),
        item.get("product_name"),
        item.get("specs"),
        item.get("quantity"),
        item.get("unit"),
        offer.get("id"),
        offer.get("supplier_name"),
        offer.get("supplier_bin"),
        offer.get("product_name"),
        offer.get("offered_quantity"),
        offer.get("quoted_unit"),
        offer.get("unit_price"),
        offer.get("total_price"),
        offer.get("currency"),
        offer.get("exchange_rate_to_kzt"),
        offer.get("vat_included"),
        offer.get("vat_rate"),
        offer.get("delivery_cost"),
        offer.get("delivery_days"),
        offer.get("availability_status"),
        offer.get("available_quantity"),
        offer.get("warranty_months"),
        offer.get("certificates") or [],
        offer.get("specification_compliant"),
        offer.get("quote_date"),
        offer.get("price_valid_until"),
        calculation.get("landed_cost_kzt"),
        calculation.get("score"),
        calculation.get("eligible"),
        offer.get("is_selected"),
        offer.get("is_recommended"),
        bool(offer_id and offer_id == str(effective_offer_id or "")),
        offer.get("match_status"),
        offer.get("source_type"),
        [risk.get("code", "") for risk in risks],
        [risk.get("message", "") for risk in risks],
        offer.get("notes"),
    ]


def build_sourcing_export(overview: Mapping[str, Any]) -> str:
    """Export every confirmed comparison row plus unresolved offers."""
    rows: list[list[Any]] = []
    for item in overview.get("items") or []:
        offers = item.get("offers") or []
        if not offers:
            rows.append(_offer_row(item, None))
            continue
        for offer in offers:
            rows.append(
                _offer_row(
                    item,
                    offer,
                    effective_offer_id=item.get("effective_offer_id"),
                )
            )
    for offer in overview.get("unmatched_offers") or []:
        rows.append(_offer_row(None, offer))
    return _write_csv(EXPORT_HEADERS, rows)


def build_supplier_import_template(items: Iterable[Mapping[str, Any]]) -> str:
    """Create one prefilled template row per tender item."""
    rows = []
    for item in items:
        rows.append(
            [
                item.get("id"),
                item.get("product_name"),
                "",
                "",
                "",
                item.get("quantity"),
                item.get("unit"),
                "",
                "",
                "KZT",
                "",
                "",
                "",
                "",
                "",
                "unknown",
                "",
                "",
                "",
                "",
                item.get("required_certificates") or [],
                "",
                "",
                "",
                "",
                "",
                "",
            ]
        )
    return _write_csv(IMPORT_TEMPLATE_HEADERS, rows)
