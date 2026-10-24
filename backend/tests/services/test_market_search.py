import json

import pytest

from app.services.market_search import (
    _decode_ddg_url,
    _matching_models,
    _parse_duckduckgo_results,
    _unique_results,
)
from app.services.product_pages import parse_product_page
from app.services.product_matching import _type_check, evaluate_product_leads


@pytest.mark.parametrize("wrapper", [
    "https://duckduckgo.com/l/?uddg=https%3A%2F%2Fshop.example.kz%2Fproduct%2Fvacuum%3Fx%3D1%26y%3D2&amp;rut=hash",
    "//duckduckgo.com/l/?uddg=https%3A%2F%2Fshop.example.kz%2Fproduct%2Fvacuum%3Fx%3D1%26y%3D2&amp;rut=hash",
    "/l/?uddg=https%3A%2F%2Fshop.example.kz%2Fproduct%2Fvacuum%3Fx%3D1%26y%3D2&amp;rut=hash",
])
def test_ddg_wrappers_resolve_to_real_vendor_without_losing_query(wrapper):
    assert _decode_ddg_url(wrapper) == "https://shop.example.kz/product/vacuum?x=1&y=2"


def test_ddg_decoder_preserves_direct_supplier_urls_and_rejects_private_redirects():
    direct = "https://shop.example.kz/product/vacuum?uddg=custom"
    assert _decode_ddg_url(direct) == direct
    assert _decode_ddg_url("https://duckduckgo.com/l/?uddg=http%3A%2F%2F127.0.0.1%2Fprivate") == ""


def test_ddg_parser_handles_attribute_order_and_independent_results_without_nested_div_layout():
    results = _parse_duckduckgo_results('''
        <article><h2><a href="https://shop.example.kz/product/1" class="highlight result__a">Philips <b>FC9734/01</b> &amp; доставка</a></h2>
        <span class="result__snippet">В наличии — <b>178 490 ₸</b></span></article>
        <article><a class='result__a' href='//duckduckgo.com/l/?uddg=https%3A%2F%2Fstore.example.kz%2Fproduct%2F2'>Другая карточка</a>
        <a href="#" class="result__snippet extra">Описание второй карточки</a></article>
        <a class="result__a" href="javascript:alert(1)">Не источник</a>
    ''')
    assert len(results) == 2
    assert results[0]["title"] == "Philips FC9734/01 & доставка"
    assert results[0]["price"] == 178490
    assert results[1]["url"] == "https://store.example.kz/product/2"
    assert results[1]["snippet"] == "Описание второй карточки"


def test_model_search_does_not_replace_requested_suffix_with_another_model():
    results = [
        {"title": "Philips FC9733/01", "url": "https://shop.example.kz/product/1"},
        {"title": "Пылесос Philips FC973401", "url": "https://shop.example.kz/product/2"},
        {"title": "Пылесос Philips", "url": "https://shop.example.kz/p/philips-fc9734-01-violet/"},
    ]
    assert [row["url"] for row in _matching_models(results, "Philips FC9734/01")] == [
        "https://shop.example.kz/product/2", "https://shop.example.kz/p/philips-fc9734-01-violet/",
    ]


def test_repeat_blocked_result_does_not_replace_already_verified_card():
    verified = {"url": "https://shop.example.kz/product/1", "page_verified": True, "seller_phone": "+77000000000"}
    blocked = {"url": verified["url"], "page_verified": False, "seller_phone": None}
    assert _unique_results([blocked, verified]) == [verified]
    assert _unique_results([verified, blocked]) == [verified]


def test_vendor_storefront_phone_spans_are_captured_but_buyer_phone_is_not():
    product = {"@type": "Product", "name": "Пылесос Philips FC9734/01", "offers": {"seller": {"name": "Поставщик"}}}
    page = parse_product_page(
        '<title>Пылесос Philips FC9734/01</title>'
        f'<script type="application/ld+json">{json.dumps(product)}</script>'
        '<div data-qaid="company_phones"><span class="notranslate">+7 (700) 111-22-33</span>'
        '<span>Телефония</span><span>+7 (706) 444-55-66</span></div>'
        '<div class="product-description">Согласовать с заказчиком +7 (701) 999-88-77</div>',
        "https://vendor.example.kz/p123-vacuum.html",
    )
    assert page["seller_phones"] == ["+7 (700) 111-22-33", "+7 (706) 444-55-66"]


def test_marketplace_platform_footer_phone_is_not_attributed_to_seller():
    page = parse_product_page(
        '<title>Пылесос Philips FC9734/01</title>'
        '<script type="application/ld+json">{"@type":"Product","name":"Пылесос Philips FC9734/01",'
        '"offers":{"seller":{"name":"Продавец","contactPoint":{"telephone":"+77001112233"}}}}</script>'
        '<footer><a href="tel:+77009998877">Поддержка маркетплейса</a></footer>',
        "https://kaspi.kz/shop/p/philips-fc9734-01-123456/",
    )
    assert page["seller_phones"] == ["+77001112233"]


def test_product_heading_can_identify_merchant_item_without_json_ld():
    page = parse_product_page(
        '<title>Пылесос Philips FC9734/01 — магазин</title>'
        '<h1 class="product_title">Пылесос Philips FC9734/01</h1>'
        '<img class="product-gallery" alt="Пылесос Philips FC9734/01" src="/uploads/vacuum.jpg">'
        '<footer><a href="tel:+77001112233">Связаться с магазином</a></footer>',
        "https://vendor.example.kz/shop/pylesos-philips-fc9734-01/",
    )
    assert page["is_product_page"] is True
    assert page["image_url"] == "https://vendor.example.kz/uploads/vacuum.jpg"
    assert page["seller_phone"] == "+77001112233"
    assert page["price"] is None


@pytest.mark.parametrize("title", [
    "Комплект для пылесоса Philips PowerPro Expert тип CP0616 серия FC9728, FC9730, FC9731, FC9732, FC9733, FC9734",
    "HEPA-фильтр для пылесоса Philips FC9734/01",
    "Насадка для пылесоса Philips FC9734/01",
])
def test_compatible_accessories_are_not_the_requested_appliance(title):
    assert _type_check("Пылесос Philips FC9734/01", title)["status"] == "mismatch"


def test_wrong_model_is_not_matched_by_the_shared_prefix():
    assert _type_check("Пылесос Philips FC9734/01", "Пылесос Philips FC9733/01")["status"] == "mismatch"
    assert _type_check("Пылесос Philips FC9734/01", "Пылесос Philips FC9733/01\nСравните также FC9734/01")["status"] == "mismatch"
    assert _type_check("Пылесос Philips FC9734/01", "Пылесос Philips FC973401")["status"] == "matched"
    assert _type_check("Пылесос Philips FC9734/01", "Пылесос Philips PowerPro")["status"] == "unknown"
    assert _type_check("Пылесос с фильтром Philips FC9734/01", "Пылесос Philips FC9734/01 с фильтром")["status"] == "matched"
    assert _type_check("Фильтр для пылесоса Philips FC9734/01", "Фильтр для пылесоса Philips FC9734/01")["status"] == "matched"


@pytest.mark.asyncio
async def test_ai_cannot_promote_compatible_spare_part_to_full_appliance(monkeypatch):
    from app.core.config import settings
    from app.services import product_matching

    monkeypatch.setattr(settings, "GOOGLE_AI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)

    async def misleading_ai(*_args):
        return {"candidates": [{"url": "https://shop.example.kz/product/filter", "checks": [
            {"id": "type", "status": "matched", "evidence": "HEPA-фильтр для пылесоса Philips FC9734/01"},
        ]}]}

    monkeypatch.setattr(product_matching, "_ask_ai", misleading_ai)
    leads = await evaluate_product_leads("Пылесос Philips FC9734/01", None, [{
        "url": "https://shop.example.kz/product/filter", "is_product_page": True, "page_verified": True,
        "evidence_text": "HEPA-фильтр для пылесоса Philips FC9734/01",
    }])
    assert leads[0]["match_status"] == "mismatch"
