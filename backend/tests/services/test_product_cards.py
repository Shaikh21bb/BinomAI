import json

import pytest

from app.services.product_matching import _compare_locally, _requirements, _type_check, evaluate_product_leads
from app.services.product_pages import is_public_url, parse_product_page


def _markup(product: dict, page_title: str) -> str:
    return (
        f"<html><head><title>{page_title}</title>"
        f'<script type="application/ld+json">{json.dumps(product, ensure_ascii=False)}</script>'
        "</head><body></body></html>"
    )


def test_concrete_product_page_extracts_real_photo_specs_and_price():
    page = parse_product_page(
        _markup(
            {
                "@type": "Product",
                "name": "Средство для туалета Утенок 500 мл",
                "description": "Удаляет ржавчину и известковый налет",
                "image": "https://images.example.kz/utenok-500.jpg",
                "additionalProperty": [{"name": "Объём", "value": "500 мл"}],
                "offers": {"price": "1250", "priceCurrency": "KZT"},
            },
            "Средство для туалета Утенок 500 мл — магазин",
        ),
        "https://shop.example.kz/p/utenok-500",
    )
    assert page["is_product_page"] is True
    assert page["image_url"] == "https://images.example.kz/utenok-500.jpg"
    assert page["characteristics"]["Объём"] == "500 мл"
    assert page["price"] == 1250


@pytest.mark.parametrize(
    "page_url",
    [
        "https://shop.example.kz/products/planka-karniznaya-100h69/",
        "https://shop.example.kz/goods/117398747-planka-karniznaya/",
        "https://shop.example.kz/catalog/krovlya/planka-karniznaya-100x69x2000/",
    ],
)
def test_vendor_product_paths_extract_main_gallery_photo_without_json_ld(page_url):
    page = parse_product_page(
        """
        <html><head><title>Планка карнизная 100х69х2000 — магазин</title>
        <meta property="og:image" content="/assets/company-logo.png"></head>
        <body><h1>Планка карнизная 100х69х2000</h1>
        <img class="logo" src="/assets/logo.svg" alt="">
        <img class="product_image" src="/coating-250.jpg" alt="Покрытие металла">
        <img class="main-gallery" src="/thumb.jpg" data-src="/uploads/planka-100x69-full.jpg"
             alt="Планка карнизная 100х69х2000">
        </body></html>
        """,
        page_url,
    )
    assert page["is_product_page"] is True
    assert page["title"] == "Планка карнизная 100х69х2000"
    assert page["image_url"] == "https://shop.example.kz/uploads/planka-100x69-full.jpg"


def test_plain_catalog_category_is_not_promoted_to_product_card():
    page = parse_product_page(
        '<h1>Кровельные материалы</h1><img class="catalog" src="/catalog/roof.jpg">',
        "https://shop.example.kz/catalog/krovlya/",
    )
    assert page["is_product_page"] is False


def test_published_inventory_count_is_separate_from_availability():
    page = parse_product_page(
        _markup(
            {"@type": "Product", "name": "Гель для посуды 500 мл",
             "offers": {"availability": "https://schema.org/InStock", "inventoryLevel": {"value": 18, "unitText": "шт"}}},
            "Гель для посуды 500 мл",
        ),
        "https://shop.example.kz/p/gel-500",
    )
    assert page["stock_quantity"] == 18
    assert page["stock_unit"] == "шт"
    available_without_count = parse_product_page(
        _markup({"@type": "Product", "name": "Гель для посуды 500 мл", "offers": {"availability": "https://schema.org/InStock"}}, "Гель для посуды 500 мл"),
        "https://shop.example.kz/p/gel-500",
    )
    assert available_without_count["stock_quantity"] is None
    assert available_without_count["availability"] == "InStock"
    stated_in_description = parse_product_page(
        _markup({"@type": "Product", "name": "Гель для посуды 500 мл", "description": "В наличии: 24 шт."}, "Гель для посуды 500 мл"),
        "https://shop.example.kz/p/gel-500",
    )
    assert stated_in_description["stock_quantity"] == 24
    sold_out = parse_product_page(
        _markup({"@type": "Product", "name": "Гель для посуды 500 мл", "offers": {"inventoryLevel": 0}}, "Гель для посуды 500 мл"),
        "https://shop.example.kz/p/gel-500",
    )
    assert sold_out["stock_quantity"] == 0


def test_search_listing_with_nested_product_is_not_a_product_card():
    page = parse_product_page(
        _markup(
            {"@type": "Product", "name": "Диспенсер для мыла Vialli 500 мл"},
            "Моющее средство 500 мл — купить в Казахстане",
        ),
        "https://satu.kz/Moyuschee-sredstvo-500ml.html",
    )
    assert page["is_product_page"] is False


def test_satu_collection_is_not_a_product_even_when_featured_product_matches():
    page = parse_product_page(
        _markup({"@type": "Product", "name": "Туалетный Утенок 515 мл"}, "Туалетный Утенок 515 мл"),
        "https://satu.kz/Tualetnyj-utenok-500-ml.html",
    )
    assert page["is_product_page"] is False


def test_private_and_local_urls_are_not_crawled():
    assert not is_public_url("http://127.0.0.1/admin")
    assert not is_public_url("http://192.168.1.1/")
    assert not is_public_url("http://localhost:8000/")
    assert is_public_url("https://shop.example.kz/p/123")


def test_requirements_keep_specs_but_not_delivery_terms():
    requirements = _requirements(
        "Моющее средство для посуды, 500 мл",
        "Для ручного мытья посуды; ГОСТ 51696-2003; Место поставки: Риддер; Срок поставки: 15 дней",
    )
    text = [row["text"] for row in requirements]
    assert "500 мл" in text
    assert "ГОСТ 51696-2003" in text
    assert not any("Риддер" in row or "15 дней" in row for row in text)


def test_package_size_matches_equivalent_units_and_detects_wrong_size():
    assert _compare_locally("500 мл", "Гель для посуды 0,5 л")["status"] == "matched"
    assert _compare_locally("500 мл", "Гель для посуды 750 мл")["status"] == "mismatch"
    assert _compare_locally("500 гр", "Гель для посуды 500 мл")["status"] == "unknown"


def test_percentage_requires_its_ingredient_on_the_same_evidence_line():
    assert _compare_locally("соляная кислота не менее 5%", "Кислота лимонная 5%")['status'] == "unknown"
    assert _compare_locally("соляная кислота не менее 5%", "Соляная кислота 5%")['status'] == "matched"
    assert _compare_locally("н-ПАВ больше 5%", "Состав: вода 5%")['status'] == "unknown"


def test_toilet_cleaner_is_not_toilet_soap():
    requirement = "Моющее средство для туалета"
    assert _type_check(requirement, "Жидкое мыло туалетное 500 мл")["status"] == "unknown"
    assert _type_check(requirement, "Средство для чистки унитаза 500 мл")["status"] == "matched"


@pytest.mark.asyncio
async def test_unproven_characteristic_prevents_full_match(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "GOOGLE_AI_API_KEY", None)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
    leads = await evaluate_product_leads(
        "Моющее средство для туалета, 500 мл",
        "Удаляет известковый налет; ГОСТ Р 51696-2003",
        [{"url": "https://shop.example.kz/p/1", "is_product_page": True, "page_verified": True,
          "evidence_text": "Моющее средство для туалета 500 мл\nОбъём: 500 мл"}],
    )
    assert leads[0]["match_status"] == "partial"
    assert any(check["status"] == "unknown" for check in leads[0]["checks"])


@pytest.mark.asyncio
async def test_matching_package_size_does_not_validate_a_different_product(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "GOOGLE_AI_API_KEY", None)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
    leads = await evaluate_product_leads(
        "Моющее средство для посуды, 500 мл",
        None,
        [{"url": "https://shop.example.kz/p/3", "is_product_page": True, "page_verified": True,
          "evidence_text": "Средство для мытья пола 500 мл"}],
    )
    assert leads[0]["checks"][0]["status"] == "unknown"
    assert leads[0]["match_status"] == "unknown"


@pytest.mark.asyncio
async def test_ai_quote_must_exist_in_source(monkeypatch):
    from app.core.config import settings
    from app.services import product_matching

    monkeypatch.setattr(settings, "GOOGLE_AI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)

    async def invented_answer(requirements, candidates):
        return {"candidates": [{"url": candidates[0]["url"], "checks": [
            {"id": "r2", "status": "matched", "evidence": "Сертификат ГОСТ Р 51696-2003 подтверждён"},
        ]}]}

    monkeypatch.setattr(product_matching, "_ask_ai", invented_answer)
    leads = await evaluate_product_leads(
        "Моющее средство для посуды, 500 мл",
        "ГОСТ Р 51696-2003",
        [{"url": "https://shop.example.kz/p/2", "is_product_page": True, "page_verified": True,
          "evidence_text": "Моющее средство для посуды 500 мл"}],
    )
    assert leads[0]["match_status"] == "partial"
    assert leads[0]["checks"][-1]["status"] == "unknown"


@pytest.mark.asyncio
async def test_ai_cannot_confirm_percentage_without_named_ingredient(monkeypatch):
    from app.core.config import settings
    from app.services import product_matching

    monkeypatch.setattr(settings, "GOOGLE_AI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)

    async def misleading_answer(requirements, candidates):
        return {"candidates": [{"url": candidates[0]["url"], "checks": [
            {"id": "r2", "status": "matched", "evidence": "Состав: 5% очищенная вода"},
        ]}]}

    monkeypatch.setattr(product_matching, "_ask_ai", misleading_answer)
    leads = await evaluate_product_leads(
        "Моющее средство для туалета, 500 мл",
        "н-ПАВ больше 5%",
        [{"url": "https://shop.example.kz/p/4", "is_product_page": True, "page_verified": True,
          "evidence_text": "Моющее средство для туалета 500 мл\nСостав: 5% очищенная вода"}],
    )
    assert leads[0]["checks"][-1]["status"] == "unknown"
