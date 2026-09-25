import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from app.db.models.product_search import ProductSearchItem
from app.db.models.project import Project
from app.db.models.sourcing import SupplierOffer
from app.services.sourcing import (
    build_comparison,
    build_rfq_draft,
    conversion_factor,
    match_line_item,
    parse_quote_file,
    quote_row_payload,
)
from app.schemas.sourcing import SupplierOfferCreate, SupplierOfferUpdate
from pydantic import ValidationError


COMPANY_ID = uuid.uuid4()
PROJECT_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


def project():
    return Project(
        id=PROJECT_ID,
        company_id=COMPANY_ID,
        created_by=USER_ID,
        name="Строительство склада",
        status="ready",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def item(name="Кабель ВВГнг 3x2.5", quantity=100, unit="м"):
    return ProductSearchItem(
        id=uuid.uuid4(),
        project_id=PROJECT_ID,
        company_id=COMPANY_ID,
        product_name=name,
        specs="ГОСТ, медь",
        unit=unit,
        quantity=quantity,
        status="ready",
        results=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def offer(line, supplier, price, compliance="compliant"):
    return SupplierOffer(
        id=uuid.uuid4(),
        project_id=PROJECT_ID,
        company_id=COMPANY_ID,
        item_id=line.id,
        created_by=USER_ID,
        supplier_name=supplier,
        original_item_name=line.product_name,
        normalized_item_name=line.product_name.lower(),
        original_unit=line.unit,
        normalized_unit="m",
        unit_price=Decimal(str(price)),
        price_quantity=Decimal("1"),
        currency="KZT",
        vat_included=True,
        quoted_quantity=Decimal("100"),
        available_quantity=Decimal("100"),
        delivery_cost=Decimal("0"),
        lead_time_days=5,
        warranty_months=12,
        certificates=["Сертификат соответствия"],
        characteristics={"ГОСТ": "подтверждён"},
        compliance_status=compliance,
        quote_date=date(2026, 9, 20),
        source_type="manual",
        match_status="matched",
        match_confidence=Decimal("1"),
        is_selected=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def test_safe_unit_conversion_rejects_different_dimensions():
    assert conversion_factor("т", "кг") == Decimal("1000")
    assert conversion_factor("см", "м") == Decimal("0.01")
    assert conversion_factor("кг", "м") is None
    assert conversion_factor("упаковка", "шт") is None


def test_name_match_requires_review_when_ambiguous():
    cable_one = item("Кабель ВВГнг 3x2.5")
    cable_two = item("Кабель ВВГнг 5x2.5")
    matched, status, confidence = match_line_item("Кабель ВВГнг", [cable_one, cable_two])
    assert matched in (cable_one, cable_two)
    assert status == "needs_review"
    assert confidence > Decimal("0.58")


def test_compliant_offer_beats_cheaper_noncompliant_offer():
    line = item()
    cheap = offer(line, "Слишком дёшево", 80, "noncompliant")
    sound = offer(line, "Проверенный поставщик", 100, "compliant")

    result = build_comparison(project(), [line], [cheap, sound], Decimal("20"), today=date(2026, 9, 23))

    row = result["items"][0]
    assert row["recommended_offer_id"] == sound.id
    assert row["selected_offer_id"] == sound.id
    assert result["summary"]["estimated_cost_kzt"] == 10000.0
    assert result["summary"]["estimated_bid_kzt"] == 12500.0
    assert result["summary"]["estimated_profit_kzt"] == 2500.0
    cheap_result = next(entry for entry in row["offers"] if entry["offer"]["id"] == cheap.id)
    assert "noncompliant" in {flag["code"] for flag in cheap_result["flags"]}


def test_suspiciously_cheap_offer_is_flagged_but_explained():
    line = item()
    offers = [offer(line, "A", 40), offer(line, "B", 100), offer(line, "C", 110)]
    result = build_comparison(project(), [line], offers, Decimal("15"), today=date(2026, 9, 23))
    cheap_result = next(entry for entry in result["items"][0]["offers"] if entry["offer"]["supplier_name"] == "A")
    assert "suspiciously_cheap" in {flag["code"] for flag in cheap_result["flags"]}


def test_moq_is_a_minimum_not_an_order_multiple():
    line = item(quantity=150)
    quoted = offer(line, "A", 10)
    quoted.moq = Decimal("100")
    quoted.available_quantity = Decimal("150")

    result = build_comparison(project(), [line], [quoted], Decimal("15"), today=date(2026, 9, 23))

    evaluated = result["items"][0]["offers"][0]
    assert evaluated["purchased_quantity"] == 150.0
    assert evaluated["landed_cost_kzt"] == 1500.0
    assert "insufficient_availability" not in {flag["code"] for flag in evaluated["flags"]}


def test_currency_aliases_normalize_before_length_validation():
    payload = SupplierOfferCreate(
        supplier_name="Supplier",
        original_item_name="Item",
        unit_price=Decimal("1"),
        currency="тенге",
        vat_included=True,
    )
    assert payload.currency == "KZT"


def test_offer_update_rejects_explicit_null_for_required_fields():
    try:
        SupplierOfferUpdate(unit_price=None)
    except ValidationError:
        pass
    else:
        raise AssertionError("unit_price=null must not be accepted")


def test_csv_import_preserves_original_values():
    content = (
        "supplier_name;item_name;unit;quantity;unit_price;currency;vat_included;compliance\n"
        "ТОО Кабель;Кабель ВВГнг 3x2.5;м;100;450,50;KZT;да;соответствует\n"
    ).encode("utf-8")
    rows = parse_quote_file("quotes.csv", content)
    payload = quote_row_payload(rows[0])
    assert payload["supplier_name"] == "ТОО Кабель"
    assert payload["original_item_name"] == "Кабель ВВГнг 3x2.5"
    assert payload["unit_price"] == Decimal("450.50")
    assert payload["vat_included"] is True
    assert payload["compliance_status"] == "compliant"


def test_csv_import_understands_spaced_noncompliance_status():
    content = (
        "supplier_name;item_name;unit_price;compliance\n"
        "ТОО Кабель;Кабель ВВГнг 3x2.5;450;не соответствует\n"
    ).encode("utf-8")
    rows = parse_quote_file("quotes.csv", content)

    assert quote_row_payload(rows[0])["compliance_status"] == "noncompliant"


def test_rfq_is_a_draft_with_required_quote_fields():
    subject, body = build_rfq_draft(
        project(),
        [item()],
        response_deadline=date(2026, 9, 30),
        delivery_location="Алматы",
        notes="Указать производителя",
    )
    assert "Строительство склада" in subject
    assert "Кабель ВВГнг" in body
    assert "НДС" in body
    assert "30.09.2026" in body
