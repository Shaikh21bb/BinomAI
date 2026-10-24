import json

import pytest

from app.services.market_search import (
    _complete_in_stock,
    _decode_ddg_url,
    _matching_models,
    _parse_duckduckgo_results,
    _primary_query,
    _relevant_candidates,
    _relevant_result,
    _search_queries,
    _unique_results,
    search_products,
)
from app.services.product_pages import parse_product_page
from app.services.product_matching import _requirements, _type_check, evaluate_product_leads


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


def test_query_variants_use_only_supplied_characteristics_and_stay_bounded():
    variants = _search_queries(
        "Жакет женский на замке из плотной вязки",
        "Жакет шерстяной; Горловина круглая. Место поставки: улица5, дом40; 2100Вт",
    )
    assert "Жакет женский" in variants
    assert 2 <= len(variants) <= 6
    assert any("шерстяной" in query for query in variants)
    assert "шерстяной" in variants[0]
    assert "Жакет женский на молнии" in variants
    assert "Жакет женский плотной вязки" in variants
    assert "Жакет женский в наличии" in variants
    assert not any("шерстяной" in query and "вязки" in query for query in variants)
    assert not any("2100" in query or "дом40" in query or "Philips" in query for query in variants)
    assert len(_search_queries("Philips FC9734/01", "Мощность2100 Вт")) <= 6
    assert len(variants) == len(set(query.casefold() for query in variants))


def test_query_slots_preserve_availability_and_type_when_many_characteristics_exist():
    variants = _search_queries(
        "Жакет женский на замке из плотной вязки",
        "Материал: шерсть; Трикотаж; Длина 80 см; Ширина 50 см; Вес 2 кг",
    )
    assert len(variants) == 6
    assert variants[-2:] == ["Жакет женский в наличии", "Жакет женский"]
    assert "Жакет женский шерсть" in variants
    assert "Жакет женский на молнии" in variants
    assert "Жакет женский плотной вязки" in variants
    assert "Жакет женский Трикотаж".casefold() in {query.casefold() for query in variants}


@pytest.mark.parametrize("override", [
    {"price": 0}, {"price": -10}, {"price": float("nan")}, {"price": float("inf")}, {"price": True},
    {"currency": None}, {"currency": " "}, {"stock_quantity": 0}, {"stock_quantity": -1},
    {"stock_quantity": float("nan")}, {"image_url": "https://images.example.kz/logo.jpg"},
    {"image_url": "https://images.example.kz/placeholder.jpg"}, {"image_url": "data:image/png;base64,abc"},
    {"seller_phone": " "}, {"seller_phone": "Позвонить"}, {"page_verified": False},
])
def test_instock_early_stop_requires_valid_published_commerce_not_truthy_fields(override):
    row = {"title": "Жакет женский", "url": "https://shop.example.kz/product/1", "is_product_page": True,
           "page_verified": True, "availability": "InStock", "image_url": "https://images.example.kz/jacket.jpg",
           "price": 50000, "currency": "KZT", "seller_phone": "+77001112233",
           "evidence_text": "Жакет женский\nМатериал: шерсть"}
    requirements = _requirements("Жакет женский", "Материал: шерсть")
    assert _complete_in_stock([row], requirements) == 1
    assert _complete_in_stock([{**row, **override}], requirements) == 0


def test_instock_early_stop_accepts_current_phone_list_but_not_type_only_confirmation():
    row = {"url": "https://shop.example.kz/product/1", "is_product_page": True, "page_verified": True,
           "availability": "InStock", "stock_quantity": None, "image_url": "https://images.example.kz/jacket.jpg",
           "price": 50000, "currency": "KZT", "seller_phones": ["", "+77001112233"],
           "evidence_text": "Жакет женский\nМатериал: шерсть"}
    assert _complete_in_stock([row], _requirements("Жакет женский", "Материал: шерсть")) == 1
    assert _complete_in_stock([row], _requirements("Жакет женский", None)) == 0


@pytest.mark.parametrize("evidence", [
    "Жакет женский\nМатериал: хлопок\nГОСТ 25295-2003",
    "Жакет женский\nМатериал: шерсть",
    "Жакет\nМатериал: шерсть\nГОСТ 25295-2003",
])
@pytest.mark.asyncio
async def test_three_commercially_complete_instock_cards_do_not_stop_with_unproven_requirements(monkeypatch, evidence):
    from unittest.mock import Mock

    import httpx

    from app.core.config import settings
    from app.services import market_search

    queries = []

    async def search(query, *_args):
        queries.append(query)
        prefix = "wrong" if len(queries) == 1 else "matched"
        return [{"title": "Жакет женский", "url": f"https://shop.example.kz/product/{prefix}-{n}"} for n in range(3)]

    async def enrich(rows):
        return [{**row, "is_product_page": True, "page_verified": True, "availability": "InStock",
                 "image_url": "https://images.example.kz/jacket.jpg", "price": 50000, "currency": "KZT", "seller_phone": "+77001112233",
                 "evidence_text": evidence if "wrong" in row["url"] else "Жакет женский\nМатериал: шерсть\nГОСТ 25295-2003"} for row in rows]

    forbidden_http = Mock(side_effect=AssertionError("Discovery must not create an HTTP client for technical checks"))

    monkeypatch.setattr(settings, "GOOGLE_CSE_API_KEY", None)
    monkeypatch.setattr(settings, "GOOGLE_AI_API_KEY", "configured-but-not-used")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "configured-but-not-used")
    monkeypatch.setattr(market_search, "_duckduckgo", search)
    monkeypatch.setattr(market_search, "enrich_product_pages", enrich)
    monkeypatch.setattr(httpx, "AsyncClient", forbidden_http)
    rows = await search_products("Жакет женский", specs="Материал: шерсть; ГОСТ 25295-2003")

    assert len(queries) == 2
    assert all("matched" in row["url"] for row in rows[:3])
    assert all("evidence_text" in row for row in rows)
    assert not any("match_status" in row for row in rows)
    forbidden_http.assert_not_called()


@pytest.mark.asyncio
async def test_three_source_verified_fully_matching_instock_cards_stop_without_extra_search(monkeypatch):
    from app.core.config import settings
    from app.services import market_search

    calls = []

    async def search(query, *_args):
        calls.append(query)
        return [{"title": "Жакет женский", "url": f"https://shop.example.kz/product/{n}"} for n in range(3)]

    async def enrich(rows):
        return [{**row, "is_product_page": True, "page_verified": True, "availability": "InStock",
                 "image_url": "https://images.example.kz/jacket.jpg", "price": 50000, "currency": "KZT", "seller_phone": "+77001112233",
                 "evidence_text": "Жакет женский\nМатериал: шерсть"} for row in rows]

    async def forbidden_fallback(*_args):
        raise AssertionError("Fully evidenced results should stop further source requests")

    monkeypatch.setattr(settings, "GOOGLE_CSE_API_KEY", None)
    monkeypatch.setattr(market_search, "_duckduckgo", search)
    monkeypatch.setattr(market_search, "_satu_search", forbidden_fallback)
    monkeypatch.setattr(market_search, "enrich_product_pages", enrich)
    rows = await search_products("Жакет женский", specs="Материал: шерсть")
    assert len(calls) == 1
    assert len(rows) == 3
    assert all(row.get("stock_quantity") is None for row in rows)


@pytest.mark.asyncio
async def test_explicit_item_closure_policy_is_forwarded_to_local_requirements_only_when_chosen(monkeypatch):
    from app.core.config import settings
    from app.services import market_search

    policies = []

    def requirements(name, specs, *, closure_policy=None):
        policies.append(closure_policy)
        return _requirements("Жакет женский", "Материал: шерсть")

    async def search(*_args):
        return [{"title": "Жакет женский", "url": f"https://shop.example.kz/product/{n}"} for n in range(3)]

    async def enrich(rows):
        return [{**row, "is_product_page": True, "page_verified": True, "availability": "InStock",
                 "image_url": "https://images.example.kz/jacket.jpg", "price": 50000, "currency": "KZT",
                 "seller_phone": "+77001112233", "evidence_text": "Жакет женский\nМатериал: шерсть"} for row in rows]

    monkeypatch.setattr(settings, "GOOGLE_CSE_API_KEY", None)
    monkeypatch.setattr(market_search, "_requirements", requirements)
    monkeypatch.setattr(market_search, "_duckduckgo", search)
    monkeypatch.setattr(market_search, "enrich_product_pages", enrich)
    await search_products("Жакет женский на замке", specs="Материал: шерсть", closure_policy="allow_alternatives")
    await search_products("Жакет женский на замке", specs="Материал: шерсть")
    assert policies == ["allow_alternatives", None]


@pytest.mark.parametrize("availability,verified", [(None, False), ("OutOfStock", True)])
@pytest.mark.asyncio
async def test_six_unusable_cards_do_not_stop_further_queries(monkeypatch, availability, verified):
    from app.core.config import settings
    from app.services import market_search

    queries = []
    reads = []

    async def search(query, *_args):
        queries.append(query)
        if len(queries) == 1:
            return [{"title": "Philips FC9734/01", "url": f"https://shop.example.kz/product/unusable-{n}"} for n in range(6)]
        return [{"title": "Philips FC9734/01", "url": "https://store.example.kz/product/available"}]

    async def enrich(rows):
        reads.extend(row["url"] for row in rows)
        return [{**row, "is_product_page": True, "page_verified": True if "available" in row["url"] else verified,
                 "availability": "InStock" if "available" in row["url"] else availability,
                 "image_url": "https://images.example.kz/photo.jpg", "price": 178490,
                 "seller_phone": "+77001112233"} for row in rows]

    async def no_results(*_args):
        return []

    monkeypatch.setattr(settings, "GOOGLE_CSE_API_KEY", None)
    monkeypatch.setattr(market_search, "_duckduckgo", search)
    monkeypatch.setattr(market_search, "_satu_search", no_results)
    monkeypatch.setattr(market_search, "enrich_product_pages", enrich)
    rows = await search_products("Philips FC9734/01", specs="Мощность2100 Вт")

    assert len(queries) >= 2
    assert rows[0]["url"] == "https://store.example.kz/product/available"
    assert len(reads) == len(set(reads))
    assert len(reads) <= 24


@pytest.mark.asyncio
async def test_search_crawl_budget_is_shared_across_all_queries(monkeypatch):
    from app.core.config import settings
    from app.services import market_search

    reads = []
    batch = 0

    async def search(*_args):
        nonlocal batch
        batch += 1
        return [{"title": "Philips FC9734/01", "url": f"https://shop.example.kz/product/{batch}-{n}"} for n in range(20)]

    async def enrich(rows):
        reads.extend(row["url"] for row in rows)
        return [{**row, "is_product_page": True, "page_verified": False} for row in rows]

    monkeypatch.setattr(settings, "GOOGLE_CSE_API_KEY", "test")
    monkeypatch.setattr(settings, "GOOGLE_CSE_ID", "test")
    monkeypatch.setattr(market_search, "_google_cse", search)
    monkeypatch.setattr(market_search, "_duckduckgo", search)
    monkeypatch.setattr(market_search, "_satu_search", search)
    monkeypatch.setattr(market_search, "enrich_product_pages", enrich)
    await search_products("Philips FC9734/01", specs="Мощность2100 Вт")
    assert len(reads) == 24
    assert len(set(reads)) == 24


@pytest.mark.asyncio
async def test_each_grounded_query_gets_read_budget_and_late_matching_cards_survive_result_cap(monkeypatch):
    from app.core.config import settings
    from app.services import market_search

    queries = []
    reads = []
    query = "Жакет женский на замке из плотной вязки"
    specs = "Материал: шерсть; Трикотаж"
    expected_queries = _search_queries(query, specs)

    async def search(search_query, *_args):
        queries.append(search_query)
        return [{"title": "Жакет женский", "url": f"https://shop.example.kz/product/{len(queries)}-{n}"} for n in range(20)]

    async def enrich(rows):
        reads.extend(row["url"] for row in rows)
        return [{**row, "is_product_page": True, "page_verified": True, "availability": "InStock",
                 "image_url": "https://images.example.kz/jacket.jpg", "price": 50000, "currency": "KZT", "seller_phone": "+77001112233",
                 "evidence_text": "Жакет женский\nЗастежка: молния\nПлотная вязка\nТрикотаж\nМатериал: "
                                  + ("шерсть" if len(queries) == len(expected_queries) else "хлопок")} for row in rows]

    async def forbidden_fallback(*_args):
        raise AssertionError("The shared read budget must prevent further fallback requests")

    monkeypatch.setattr(settings, "GOOGLE_CSE_API_KEY", None)
    monkeypatch.setattr(market_search, "_duckduckgo", search)
    monkeypatch.setattr(market_search, "_satu_search", forbidden_fallback)
    monkeypatch.setattr(market_search, "enrich_product_pages", enrich)
    rows = await search_products(query, specs=specs)

    assert queries == expected_queries
    assert 12 < len(reads) == len(set(reads)) <= 24
    assert len(rows) == 12
    assert all(f"/product/{len(expected_queries)}-" in row["url"] for row in rows[:3])


def test_grounded_same_vendor_product_dedup_preserves_variants_and_other_stores():
    rows = [
        {"url": "https://store.example.kz/old-path?utm_source=google", "page_verified": True,
         "is_product_page": True, "product_sku": "sku1", "availability": "OutOfStock"},
        {"url": "https://store.example.kz/product/new-path", "page_verified": True,
         "is_product_page": True, "product_sku": "sku1", "availability": "InStock"},
        {"url": "https://another.example.kz/product/new-path", "page_verified": True,
         "is_product_page": True, "product_sku": "sku1", "availability": "InStock"},
        {"url": "https://store.example.kz/product/new-path?size=44", "page_verified": True,
         "is_product_page": True, "product_sku": "sku1", "availability": "InStock"},
    ]
    unique = _unique_results(rows)
    assert len(unique) == 3
    assert unique[0]["availability"] == "InStock"
    assert len(_unique_results([
        {"url": "https://store.example.kz/alias", "page_verified": True, "canonical_url": "https://store.example.kz/product/main"},
        {"url": "https://store.example.kz/product/main", "page_verified": True},
    ])) == 1


def test_localized_international_store_is_eligible_without_loosening_type_gate():
    assert _relevant_result({"title": "Жакет женский", "url": "https://shop.example.com/kz/ru/p/123"}, "Жакет женский")
    assert not _relevant_result({"title": "Корм для животных", "url": "https://shop.example.com/kz/ru/p/123"}, "Жакет женский")


def test_repeat_blocked_result_does_not_replace_already_verified_card():
    verified = {"url": "https://shop.example.kz/product/1", "page_verified": True, "seller_phone": "+77000000000"}
    blocked = {"url": verified["url"], "page_verified": False, "seller_phone": None}
    assert _unique_results([blocked, verified]) == [verified]
    assert _unique_results([verified, blocked]) == [verified]


@pytest.mark.parametrize("title", [
    "Чехол MILDOM 60x100 см", "Боди женское", "Комплект желтый", "Вешалка для жакета",
    "Перчатки женские", "Манекен женский", "Корм Jarvi", "Пуловер женский",
])
def test_unrelated_marketplace_cards_are_not_jackets_even_with_a_price(title):
    row = {"title": title, "price": 2000, "url": "https://kaspi.kz/shop/p/unrelated-123456/"}
    assert not _relevant_result(row, "Жакет женский на замке из плотной вязки")


def test_generic_query_keeps_the_type_and_supported_inflected_titles():
    query = "Жакет женский на замке из плотной вязки"
    assert _primary_query(query) == "Жакет женский"
    assert _primary_query("Philips FC9734/01") == "Philips FC9734/01"
    assert _relevant_result({"title": "Жакет женский трикотажный на молнии", "url": "https://shop.example.kz/product/1"}, query)
    assert not _relevant_result({"title": "Жакет мужской", "url": "https://shop.example.kz/product/2"}, query)


def test_transliterated_vendor_slugs_keep_genuine_types_but_not_their_accessories():
    from app.services.market_search import _satu_product_results

    rows = _satu_product_results(
        '<a href="/p123456789-zhaket-zhenskij-trikotazhnyj.html">Жакет</a>'
        '<a href="/p123456780-chehol-dlya-zhaketa.html">Чехол</a>'
    )
    relevant = _relevant_candidates(rows, "Жакет женский на замке из плотной вязки")
    assert [row["url"] for row in relevant] == ["https://satu.kz/p123456789-zhaket-zhenskij-trikotazhnyj.html"]


@pytest.mark.parametrize("title", ["Средство для мытья посуды Fairy 500 мл", "Гель для посуды 500 мл"])
def test_requested_detergent_purpose_is_not_mistaken_for_an_accessory(title):
    assert _relevant_result({"title": title, "url": "https://shop.example.kz/product/1"}, "Моющее средство для посуды")


@pytest.mark.asyncio
async def test_all_discovery_sources_filter_before_and_after_page_enrichment(monkeypatch):
    from app.core.config import settings
    from app.services import market_search

    query = "Жакет женский на замке из плотной вязки"
    seen_queries = []
    enrichment_titles = []
    unrelated = {"title": "Корм Jarvi", "price": 2000, "url": "https://kaspi.kz/shop/p/feed-123456/"}
    candidate = {"title": "Жакет женский", "url": "https://kaspi.kz/shop/p/jacket-123456/"}

    async def search(search_query, *_args):
        seen_queries.append(search_query)
        return [dict(unrelated), dict(candidate)]

    async def enrich(rows):
        enrichment_titles.extend(row["title"] for row in rows)
        # A search hit can lead to a replaced or redirected unrelated product.
        return [{**row, "title": "Манекен женский", "is_product_page": True, "page_verified": True} for row in rows]

    monkeypatch.setattr(settings, "GOOGLE_CSE_API_KEY", "test")
    monkeypatch.setattr(settings, "GOOGLE_CSE_ID", "test")
    monkeypatch.setattr(market_search, "_google_cse", search)
    monkeypatch.setattr(market_search, "_duckduckgo", search)
    monkeypatch.setattr(market_search, "_satu_search", search)
    monkeypatch.setattr(market_search, "enrich_product_pages", enrich)
    rows = await search_products(query)

    assert seen_queries[0] == "Жакет женский"
    assert enrichment_titles and all(title == "Жакет женский" for title in enrichment_titles)
    assert rows and all(not row.get("is_product_page") for row in rows)
    assert not _relevant_candidates([unrelated], query)


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
    from unittest.mock import Mock

    import httpx

    from app.core.config import settings

    monkeypatch.setattr(settings, "GOOGLE_AI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)

    forbidden_http = Mock(side_effect=AssertionError("Configured AI keys must not trigger a matching HTTP client"))

    monkeypatch.setattr(httpx, "AsyncClient", forbidden_http)
    leads = await evaluate_product_leads("Пылесос Philips FC9734/01", None, [{
        "url": "https://shop.example.kz/product/filter", "is_product_page": True, "page_verified": True,
        "evidence_text": "HEPA-фильтр для пылесоса Philips FC9734/01",
    }])
    assert leads[0]["match_status"] == "mismatch"
    forbidden_http.assert_not_called()
