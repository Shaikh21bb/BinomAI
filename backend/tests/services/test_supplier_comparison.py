from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
import uuid

from app.services.supplier_comparison import (
    build_rfq_draft,
    calculate_offer,
    compare_offers,
    conversion_factor,
    match_tender_item,
    normalize_currency,
    normalize_name,
    normalize_unit,
)


def item(**values):
    defaults = {
        "id": uuid.uuid4(),
        "product_name": "Цемент М500",
        "specs": "ГОСТ 10178",
        "unit": "кг",
        "quantity": 1000,
        "required_certificates": [],
        "warranty_required": False,
        "desired_delivery_date": None,
    }
    defaults.update(values)
    return SimpleNamespace(**defaults)


def offer(**values):
    defaults = {
        "id": uuid.uuid4(),
        "supplier_name": "Поставщик",
        "product_name": "Цемент М500",
        "quoted_unit": "кг",
        "offered_quantity": 1000,
        "unit_conversion_factor": None,
        "unit_price": Decimal("100"),
        "total_price": None,
        "currency": "KZT",
        "exchange_rate_to_kzt": None,
        "exchange_rate_date": None,
        "vat_included": True,
        "vat_rate": Decimal("12"),
        "min_order_quantity": None,
        "availability_status": "available",
        "available_quantity": 1000,
        "delivery_cost": Decimal("0"),
        "delivery_days": 2,
        "warranty_months": None,
        "certificates": [],
        "specification_compliant": True,
        "quote_date": date(2026, 9, 1),
        "price_valid_until": date(2026, 12, 1),
        "source_type": "manual",
        "match_status": "confirmed",
        "is_selected": False,
    }
    defaults.update(values)
    return SimpleNamespace(**defaults)


def test_normalization_and_safe_unit_conversion():
    assert normalize_name("  Цемент—М500 ") == "цемент м500"
    assert normalize_unit("м²") == "м2"
    assert normalize_currency("₸") == "KZT"
    assert conversion_factor("т", "кг") == Decimal("1000")
    assert conversion_factor("м3", "кг") is None


def test_landed_cost_includes_conversion_vat_and_delivery():
    result = calculate_offer(
        item(),
        offer(
            quoted_unit="т",
            offered_quantity=1,
            unit_price=Decimal("100000"),
            vat_included=False,
            vat_rate=Decimal("12"),
            delivery_cost=Decimal("5000"),
            available_quantity=1,
        ),
        today=date(2026, 9, 25),
    )
    assert result.conversion_factor == Decimal("1000")
    assert result.purchase_quantity == Decimal("1")
    assert result.unit_price_kzt == Decimal("112")
    assert result.landed_cost_kzt == Decimal("117600")
    assert result.eligible is True


def test_incompatible_unit_and_missing_fx_block_recommendation():
    result = calculate_offer(
        item(),
        offer(quoted_unit="м3", currency="USD", exchange_rate_to_kzt=None),
        today=date(2026, 9, 25),
    )
    codes = {risk["code"] for risk in result.risks}
    assert "unit_incompatible" in codes
    assert "currency_rate_missing" in codes
    assert result.eligible is False


def test_ranking_does_not_choose_cheapest_noncompliant_offer():
    cheap_bad = offer(supplier_name="Слишком дёшево", unit_price=Decimal("30"), specification_compliant=False)
    compliant = offer(supplier_name="Надёжный", unit_price=Decimal("95"))
    expensive = offer(supplier_name="Дорогой", unit_price=Decimal("120"))
    ranked = compare_offers(item(), [cheap_bad, compliant, expensive])
    assert ranked[0].offer.supplier_name == "Надёжный"
    assert ranked[0].eligible is True
    bad = next(result for result in ranked if result.offer is cheap_bad)
    assert bad.eligible is False
    assert any(risk["code"] == "suspiciously_cheap" for risk in bad.risks)


def test_required_documents_warranty_and_deadline_are_flagged():
    result = calculate_offer(
        item(
            required_certificates=["Сертификат соответствия"],
            warranty_required=True,
            desired_delivery_date=date(2026, 9, 28),
        ),
        offer(delivery_days=10, certificates=[], warranty_months=None),
        today=date(2026, 9, 25),
    )
    codes = {risk["code"] for risk in result.risks}
    assert {"certificates_missing", "warranty_missing", "deadline_risk"}.issubset(codes)


def test_quote_expiring_before_tender_deadline_is_not_recommended():
    result = calculate_offer(
        item(),
        offer(price_valid_until=date(2026, 9, 29)),
        project_deadline=datetime(2026, 10, 1, tzinfo=timezone.utc),
        today=date(2026, 9, 25),
    )
    assert any(risk["code"] == "price_expires_before_tender" for risk in result.risks)
    assert result.eligible is False


def test_ambiguous_matching_is_left_for_review():
    items = [item(product_name="Кабель ВВГ 3x2.5"), item(product_name="Кабель ВВГ 3x4")]
    matched, candidates, status = match_tender_item("Кабель ВВГ", items)
    assert matched is None
    assert status == "review"
    assert len(candidates) == 2


def test_rfq_is_a_draft_and_contains_required_terms():
    project = SimpleNamespace(name="Ремонт школы", deadline_at=datetime(2026, 10, 10, tzinfo=timezone.utc))
    draft = build_rfq_draft(project, [item(required_certificates=["СТ-KZ"])])
    assert "Ремонт школы" in draft["subject"]
    assert "Цемент М500" in draft["body"]
    assert "СТ-KZ" in draft["body"]
    assert "не является заказом" in draft["body"]
