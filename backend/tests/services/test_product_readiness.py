"""Synthetic evidence contracts; these fixtures are not real supplier offers."""

from copy import deepcopy
from decimal import Decimal

import pytest

from app.services.product_readiness import annotate_order_readiness, assess_order_quantity


def _source(**changes):
    return {
        "url": "https://vendor.example.kz/product/test", "is_product_page": True, "page_verified": True,
        "variant_status": "single", "availability": "InStock", "stock_quantity": 24, "stock_unit": "шт",
        "min_order_quantity": 5, "min_order_unit": "шт", "price": 1250, "currency": "KZT",
        "price_quantity": 1, "price_unit": "шт", "price_basis_status": "published",
        "wholesale_terms": "Оптовая цена для партии от 5 шт.", "image_url": "https://vendor.example.kz/product/photo.jpg",
        "seller_phone": "+77001112233", "match_status": "matched",
        "checks": [{"id": "type", "requirement": "Товар", "status": "matched"},
                   {"id": "r1", "requirement": "Объём 500 мл", "status": "matched", "evidence": "Объём 500 мл"}],
        **changes,
    }


@pytest.mark.parametrize("name", ["Моющее средство", "Пылесос", "Кабель"])
def test_general_order_gate_is_not_garment_specific(name):
    lead = _source(title=name)
    result = annotate_order_readiness([lead], 20, "шт")[0]
    assert result["order_readiness"]["status"] == "ready"
    assert result["order_readiness"]["quantity"]["status"] == "enough"


@pytest.mark.parametrize("changes,expected", [
    ({"stock_quantity": None}, "unknown"), ({"stock_quantity": 19}, "shortage"),
    ({"stock_unit": "упак"}, "unknown"), ({"stock_unit": "ед."}, "unknown"),
    ({"stock_quantity": True}, "unknown"), ({"stock_quantity": float("nan")}, "unknown"),
    ({"stock_quantity": float("inf")}, "unknown"), ({"stock_quantity": -1}, "unknown"),
    ({"availability": "PreOrder"}, "unknown"), ({"availability": "OutOfStock"}, "unknown"),
    ({"min_order_quantity": None}, "unknown"), ({"min_order_unit": None}, "unknown"),
    ({"min_order_quantity": 25}, "shortage"), ({"min_order_unit": "упак"}, "unknown"),
])
def test_instock_never_proves_missing_or_incompatible_order_data(changes, expected):
    assert assess_order_quantity(_source(**changes), 20, "шт")["status"] == expected


@pytest.mark.parametrize("quantity,unit", [(None, "шт"), (True, "шт"), (-1, "шт"), (20, None), (20, "ед.")])
def test_order_needs_valid_requested_quantity_and_explicit_unit(quantity, unit):
    assert annotate_order_readiness([_source()], quantity, unit)[0]["order_readiness"]["status"] != "ready"


@pytest.mark.parametrize("unit", ["кг", "м", "м2", "л", "комплект", "Дана"])
def test_explicit_same_units_work_for_other_product_categories(unit):
    source = _source(stock_unit=unit, min_order_unit=unit, price_unit=unit)
    assert annotate_order_readiness([source], Decimal("20"), unit)[0]["order_readiness"]["status"] == "ready"


@pytest.mark.parametrize("changes,gap", [
    ({"variant_status": "ambiguous"}, "variant"), ({"variant_status": None}, "variant"),
    ({"wholesale_terms": None}, "wholesale"), ({"price_basis_status": "unknown"}, "price-basis"),
    ({"price_unit": "упак"}, "price-basis"), ({"price_quantity": 50}, "price-basis"),
    ({"price": 0}, "price"), ({"price": float("nan")}, "price"),
    ({"seller_phone": None}, "phone"), ({"seller_phone": "+7"}, "phone"),
    ({"image_url": "https://vendor.example.kz/logo.png"}, "photo"),
    ({"page_verified": False}, "page"),
])
def test_price_photo_contact_wholesale_and_variant_are_independent_requirements(changes, gap):
    result = annotate_order_readiness([_source(**changes)], 20, "шт")[0]["order_readiness"]
    assert result["status"] != "ready"
    assert gap in {item["code"] for item in result["gaps"]}


def test_gost_mention_link_or_forged_verified_status_are_not_document_verification():
    for certificate_status in ("claim_only", "document_linked", "verified"):
        lead = _source(certificate_status=certificate_status, certificate_documents=[{
            "url": "https://vendor.example.kz/certificate.pdf", "status": "verified",
        }], order_readiness={"status": "ready"})
        lead["checks"].append({"id": "gost", "requirement": "ГОСТ 25295-2003", "status": "matched", "evidence": "Соответствует ГОСТ 25295-2003"})
        checked = annotate_order_readiness([lead], 20, "шт")[0]
        assert checked["checks"][-1]["status"] == "unknown"
        assert checked["checks"][-1]["evidence"] == "Соответствует ГОСТ 25295-2003"
        assert checked["match_status"] == "partial"
        assert checked["order_readiness"]["status"] == "needs_confirmation"
        assert "certificate" in {gap["code"] for gap in checked["order_readiness"]["gaps"]}


def test_reannotation_is_bound_to_current_order_not_previous_readiness():
    lead = annotate_order_readiness([_source()], 20, "шт")[0]
    checked = annotate_order_readiness([deepcopy(lead)], 25, "шт")[0]
    assert checked["order_readiness"]["status"] == "not_suitable"
    assert checked["order_readiness"]["quantity"]["requested_quantity"] == 25


def test_no_implicit_conversion_between_grams_kilograms_or_packs_pieces():
    assert assess_order_quantity(_source(stock_quantity=20000, stock_unit="г", min_order_unit="г"), 20, "кг")["status"] == "unknown"
    assert assess_order_quantity(_source(stock_quantity=20000, stock_unit="упак", min_order_unit="упак"), 20, "шт")["status"] == "unknown"


@pytest.mark.parametrize("bad_unit,requested", [("штукатурка", "шт"), ("комплектующие", "комплект"), ("грамматика", "г"), ("метрология", "м")])
def test_unit_prefix_is_not_an_actual_unit(bad_unit, requested):
    row = _source(stock_unit=bad_unit, min_order_unit=requested, price_unit=requested)
    assert assess_order_quantity(row, 20, requested)["status"] == "unknown"
    assert annotate_order_readiness([row], 20, requested)[0]["order_readiness"]["status"] != "ready"
