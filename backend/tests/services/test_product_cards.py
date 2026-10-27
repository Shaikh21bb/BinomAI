import json
from unittest.mock import Mock

import httpx
import pytest

from app.services.product_matching import _compare_locally, _requirements, _type_check, evaluate_product_leads
from app.services.market_search import _satu_product_results, enrich_product_pages
from app.services.product_pages import is_public_url, looks_like_product_url, parse_product_page


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


def test_scoped_main_product_description_and_attribute_rows_supply_real_requirements():
    markup = _markup({"@type": "Product", "name": "Шерстяной жакет", "description": "Купить онлайн"}, "Шерстяной жакет").replace(
        "</body>", '''
        <h1>Шерстяной жакет</h1>
        <div class="ItemDescription-module__abc__root">
          <h3>Описание</h3><p>Однобортный жакет из костюмной шерсти. Застёжка на пуговицах. Два кармана с клапанами.</p>
          <div class="ItemDescription-module__abc__attrRow"><p class="ItemDescription-module__abc__attrLabel">Пол</p><p class="ItemDescription-module__abc__attrValue">женщины</p></div>
          <div class="ItemDescription-module__abc__attrRow"><p class="ItemDescription-module__abc__attrLabel">Материал</p><p class="ItemDescription-module__abc__attrValue"><span>Шерсть</span></p></div>
          <div class="ItemDescription-module__abc__attrRow"><p class="ItemDescription-module__abc__attrLabel">Состав</p><p class="ItemDescription-module__abc__attrValue">Шерсть100%</p></div>
          <h3>Доставка и возврат</h3><p>Пример товара для обмена: ГОСТ 25295-2003. Плотная вязка.</p>
        </div>
        <section class="recommendations"><div class="ItemDescription-module__abc__root"><p>Длинный рукав. Плотная вязка. ГОСТ 25295-2003</p>
          <div class="ItemDescription-module__abc__attrRow"><p class="ItemDescription-module__abc__attrLabel">Застёжка</p><p class="ItemDescription-module__abc__attrValue">Молния</p></div></div></section>
        </body>''',
    )
    page = parse_product_page(markup, "https://fashion.example.kz/item/123")
    assert page["characteristics"] == {"Пол": "женщины", "Материал": "Шерсть", "Состав": "Шерсть100%"}
    assert "Застёжка на пуговицах" in page["description"]
    assert "Купить онлайн" not in page["description"]
    assert "Доставка и возврат" not in page["description"]
    assert not any(term in page["evidence_text"] for term in ("Длинный рукав", "ГОСТ", "Плотная вязка", "Молния"))


def test_product_details_ignore_preheading_navigation_and_unscoped_attributes():
    markup = _markup({"@type": "Product", "name": "Жакет", "description": "Описание основного товара"}, "Жакет").replace(
        "</body>", '''<nav><div class="product-description">ГОСТ 25295-2003</div></nav>
        <h1>Жакет</h1><div class="attrRow"><p class="attrLabel">Пол</p><p class="attrValue">женский</p></div>
        <div class="product-description"><p>Основной товар: карманы отсутствуют.</p></div></body>''',
    )
    page = parse_product_page(markup, "https://fashion.example.kz/item/123")
    assert "карманы отсутствуют" in page["description"]
    assert not page["characteristics"]
    assert "ГОСТ" not in page["evidence_text"]


def test_related_product_tables_cannot_supply_main_product_certification_or_material():
    markup = _markup({"@type": "Product", "name": "Жакет"}, "Жакет").replace(
        "</body>", '''<h1>Жакет</h1><table><tr><td>Материал</td><td>Хлопок</td></tr></table>
        <section class="related products"><h1>Жакет женский</h1><table>
        <tr><td>Материал</td><td>Шерсть</td></tr><tr><td>ГОСТ</td><td>25295-2003</td></tr>
        </table></section></body>''',
    )
    page = parse_product_page(markup, "https://fashion.example.kz/item/123")
    assert page["characteristics"] == {"Материал": "Хлопок"}
    assert "ГОСТ" not in page["evidence_text"]


@pytest.mark.parametrize("context", ['id="recommendations"', 'data-testid="related-products"'])
def test_recommendation_identifiers_exclude_both_table_and_component_evidence(context):
    markup = _markup({"@type": "Product", "name": "Жакет"}, "Жакет").replace(
        "</body>", f'''<h1>Жакет</h1><section {context}>
        <table><tr><td>Сертификат</td><td>ГОСТ 25295-2003</td></tr></table>
        <div class="product-description"><p>ГОСТ 25295-2003</p></div></section></body>''',
    )
    page = parse_product_page(markup, "https://fashion.example.kz/item/123")
    assert "ГОСТ" not in page["evidence_text"]
    assert not page["characteristics"]


def test_delivery_sections_cannot_supply_certificates_via_tables_or_attribute_rows():
    markup = _markup({"@type": "Product", "name": "Жакет"}, "Жакет").replace(
        "</body>", '''<h1>Жакет</h1><div class="product-description"><h3>Описание</h3><p>Основной жакет</p>
        <h3>Характеристики</h3><div class="attrRow"><p class="attrLabel">Материал</p><p class="attrValue">Шерсть</p></div>
        <h3>Доставка и возврат</h3><p>Пример другого товара для обмена:</p>
        <div class="attrRow"><p class="attrLabel">Сертификат</p><p class="attrValue">ГОСТ 25295-2003</p></div>
        <table><tr><td>Сертификат</td><td>ГОСТ 25295-2003</td></tr></table></div></body>''',
    )
    page = parse_product_page(markup, "https://fashion.example.kz/item/123")
    assert page["characteristics"] == {"Материал": "Шерсть"}
    assert "ГОСТ" not in page["evidence_text"]


def test_main_woocommerce_price_and_stock_do_not_leak_from_cart_or_related_products():
    page = parse_product_page('''
        <title>Пылесос Philips FC9734/01</title>
        <header><p class="price">0 ₸</p></header>
        <div data-elementor-type="product" class="product type-product instock">
          <h1 class="product_title">Пылесос Philips FC9734/01</h1>
          <img src="/vacuum.jpg" alt="Пылесос Philips FC9734/01">
          <div data-widget_type="woocommerce-product-price.default"><p class="price">
            <del>199 990 ₸</del><ins>178 490&nbsp;₸</ins></p></div>
          <span class="sku">FC9734/01</span>
          <section class="related products"><p class="stock out-of-stock">Нет в наличии</p><p class="price">25 190 ₸</p></section>
        </div>
    ''', "https://vendor.example.kz/shop/philips-fc9734-01/")
    assert page["price"] == 178490
    assert page["currency"] == "KZT"
    assert page["availability"] == "InStock"
    assert page["stock_quantity"] is None
    assert page["product_sku"] == "FC9734/01"


def test_related_instock_and_buy_button_cannot_override_main_outofstock_or_unknown():
    markup = '''
        <title>Пылесос Philips FC9734/01</title>
        <div class="product type-product outofstock">
          <h1 class="product_title">Пылесос Philips FC9734/01</h1><img src="/vacuum.jpg">
          <p class="price">178 490 ₸</p><button>Купить</button>
          <ul><li class="product type-product instock"><p class="price">25 000 ₸</p></li></ul>
        </div>
    '''
    page = parse_product_page(markup, "https://vendor.example.kz/shop/philips-fc9734-01/")
    assert page["availability"] == "OutOfStock"
    assert page["stock_quantity"] is None
    assert page["price"] == 178490
    unknown = parse_product_page(markup.replace("type-product outofstock", "type-product"), "https://vendor.example.kz/shop/philips-fc9734-01/")
    assert unknown["availability"] is None


@pytest.mark.parametrize("price,expected", [("178\u00a0490", 178490), ("178\u202f490,50", 178490.5), ("NaN", None), ("Infinity", None), ("-5", None)])
def test_published_prices_handle_unicode_spacing_without_nonfinite_or_negative_values(price, expected):
    page = parse_product_page(_markup({"@type": "Product", "name": "Пылесос Philips FC9734/01", "offers": {"price": price, "priceCurrency": "KZT"}}, "Пылесос Philips FC9734/01"), "https://vendor.example.kz/p/philips-fc9734-01")
    assert page["price"] == expected


def test_visible_negative_stock_wins_over_stale_structured_positive_stock():
    markup = _markup({"@type": "Product", "name": "Пылесос Philips FC9734/01", "offers": {"availability": "https://schema.org/InStock"}}, "Пылесос Philips FC9734/01").replace(
        "</body>", '<div class="product type-product outofstock"><h1 class="product_title">Пылесос Philips FC9734/01</h1><p class="stock">Нет в наличии</p></div></body>',
    )
    page = parse_product_page(markup, "https://vendor.example.kz/p/philips-fc9734-01")
    assert page["availability"] == "OutOfStock"
    assert page["stock_quantity"] is None


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


@pytest.mark.parametrize("url", [
    "https://www.flip.kz/catalog?subsection=7989",
    "https://www.olx.kz/moda-i-stil/zhenskaya-odezhda/zhenskie-pidzhaki-zhakety/q-жакет/",
])
def test_collection_embedded_product_price_and_stock_are_not_a_concrete_item(url):
    page = parse_product_page(_markup({
        "@type": "Product", "name": "Женские пиджаки и жакеты", "image": "https://images.example.kz/jacket.jpg",
        "offers": {"price": "700", "priceCurrency": "KZT", "availability": "https://schema.org/InStock"},
    }, "Женские пиджаки и жакеты"), url)
    assert page["is_product_page"] is False
    assert "price" not in page
    assert "availability" not in page


@pytest.mark.parametrize("url", [
    "https://fashion.example.kz/catalog/cat-zakety-38356/tissue-serst",
    "https://fashion.example.kz/catalog/category-jackets/material-wool/",
    "https://fashion.example.kz/collections/wool-jackets/",
])
def test_faceted_collection_cannot_borrow_a_featured_products_commerce(url):
    name = "Жакеты из шерсти — скидки до 70%"
    page = parse_product_page(_markup({
        "@type": "Product", "name": name, "sku": "featured-123",
        "url": "https://fashion.example.kz/products/jacket-123/",
        "image": "https://images.example.kz/featured-jacket.jpg",
        "offers": {"price": "19538", "priceCurrency": "KZT", "availability": "https://schema.org/InStock"},
    }, name), url)
    assert page == {"is_product_page": False, "page_verified": True}
    assert not looks_like_product_url(url)


@pytest.mark.parametrize("schema", [
    {"@type": "CollectionPage"},
    {"@type": "https://schema.org/ItemList"},
    {"@type": "WebPage", "mainEntity": {"@type": "ItemList"}},
])
def test_collection_schema_is_not_a_detail_even_at_a_product_shaped_url(schema):
    product = {
        "@type": "Product", "name": "Шерстяной жакет",
        "offers": {"price": "19538", "availability": "https://schema.org/InStock"},
    }
    markup = _markup({"@graph": [schema, product]}, "Шерстяной жакет").replace(
        "</body>", '<h1>Шерстяной жакет</h1><img src="/jacket.jpg"></body>',
    )
    page = parse_product_page(markup, "https://fashion.example.kz/products/wool-jackets/")
    assert page == {"is_product_page": False, "page_verified": True}


def test_own_detail_identity_survives_listing_context_and_ignores_featured_product():
    url = "https://fashion.example.kz/catalog/cat-jackets/wool-jacket-123/"
    name = "Жакет шерстяной Model 123"
    markup = _markup({"@graph": [
        {"@type": "CollectionPage", "mainEntity": {"@type": "ItemList"}},
        {"@type": "Product", "name": "Другой жакет", "url": "https://fashion.example.kz/products/other/",
         "offers": {"price": "1", "availability": "https://schema.org/OutOfStock"}},
        {"@type": "Product", "name": name, "url": url, "sku": "123",
         "offers": {"price": "19538", "priceCurrency": "KZT", "availability": "https://schema.org/InStock"}},
    ]}, name).replace("</body>", f'<h1 class="product_title">{name}</h1><img src="/jacket.jpg"></body>')
    page = parse_product_page(markup, url)
    assert page["is_product_page"] is True
    assert page["product_sku"] == "123"
    assert page["price"] == 19538
    assert page["availability"] == "InStock"


def test_detail_product_breadcrumb_item_list_is_not_a_collection_context():
    page = parse_product_page(_markup({
        "@type": "WebPage", "breadcrumb": {"@type": "ItemList"},
        "mainEntity": {"@type": "Product", "name": "Шерстяной жакет", "offers": {"price": "19538"}},
    }, "Шерстяной жакет"), "https://fashion.example.kz/item/123")
    assert page["is_product_page"] is True
    assert page["price"] == 19538


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


@pytest.mark.parametrize("level,expected_quantity,expected_unit", [
    ({"value": "2,5", "unitCode": "KGM"}, 2.5, "кг"),
    ({"value": 18, "unitCode": "H87"}, 18, "шт"),
    ({"value": 18, "unitCode": "PCE"}, 18, "шт"),
    ({"value": 18, "unitCode": "C62"}, 18, "ед."),
    ({"value": "12.75", "unitText": "м"}, 12.75, "м"),
    ({"value": 4, "unitCode": "UNKNOWN"}, 4, None),
    ({"value": 4, "unitText": "кг", "unitCode": "H87"}, 4, None),
    (18, 18, None),
    (True, None, None),
    ("NaN", None, None),
    ("Infinity", None, None),
    (-1, None, None),
    (1000001, None, None),
])
def test_inventory_decimals_units_and_bounds_never_invent_pieces(level, expected_quantity, expected_unit):
    page = parse_product_page(_markup({"@type": "Product", "name": "Кабель ABC", "offers": {"inventoryLevel": level}}, "Кабель ABC"), "https://shop.example.kz/p/cable")
    assert page["stock_quantity"] == expected_quantity
    assert page["stock_unit"] == expected_unit
    assert bool(page["stock_evidence"]) == (expected_quantity is not None)


def test_scoped_visible_decimal_stock_and_minimum_order_are_distinct_from_buy_buttons():
    markup = _markup({"@type": "Product", "name": "Кабель ABC"}, "Кабель ABC").replace("</body>", '''
      <nav>В наличии: 999 шт. Минимальный заказ: 500 шт. Оптовая цена</nav>
      <div class="product type-product"><h1 class="product_title">Кабель ABC</h1>
        <p class="stock">В наличии: 22,5 м</p><button>Купить 100</button>
        <div class="product-description"><p>Минимальная партия: 2,5 м. Продаём оптом.</p></div>
      </div></body>''')
    page = parse_product_page(markup, "https://shop.example.kz/p/cable")
    assert page["stock_quantity"] == 22.5
    assert page["stock_unit"] == "м"
    assert page["stock_evidence"] == "В наличии: 22,5 м"
    assert page["min_order_quantity"] == 2.5
    assert page["min_order_unit"] == "м"
    assert page["wholesale_terms"] == "Продаём оптом."


def test_structured_minimum_order_has_its_own_unit_and_unknown_does_not_default_to_one():
    page = parse_product_page(_markup({"@type": "Product", "name": "Кабель ABC", "offers": {
        "inventoryLevel": {"value": 50, "unitCode": "MTR"},
        "eligibleQuantity": {"minValue": "2.5", "unitCode": "MTR"},
    }}, "Кабель ABC"), "https://shop.example.kz/p/cable")
    assert (page["min_order_quantity"], page["min_order_unit"]) == (2.5, "м")
    unknown = parse_product_page(_markup({"@type": "Product", "name": "Кабель ABC"}, "Кабель ABC"), "https://shop.example.kz/p/cable")
    assert unknown["min_order_quantity"] is None
    assert unknown["min_order_unit"] is None
    assert unknown["wholesale_terms"] is None


@pytest.mark.parametrize("description", ["Не продаём оптом.", "Оптовая цена отсутствует.", "Оптовая цена не указана.", "Это не является оптовой ценой.", "Not wholesale.", "No wholesale orders.", "Оптовые заказы не принимаем.", "С оптовыми заказами не работаем.", "Не работаем с оптом."])
def test_negated_wholesale_claims_do_not_publish_wholesale_terms(description):
    page = parse_product_page(_markup({"@type": "Product", "name": "Товар ABC", "description": description}, "Товар ABC"), "https://shop.example.kz/p/item")
    assert page["wholesale_terms"] is None


def test_recommendation_identifiers_and_navigation_cannot_supply_visible_stock():
    markup = '<title>Товар ABC</title><div class="product type-product"><h1 class="product_title">Товар ABC</h1><section id="recommendations"><p class="stock">В наличии: 999 шт</p></section><nav><p class="stock">В наличии: 888 шт</p></nav></div>'
    page = parse_product_page(markup, "https://shop.example.kz/p/item")
    assert page["stock_quantity"] is None
    assert page["availability"] is None


def test_conflicting_stock_or_minimum_order_publications_stay_unknown():
    page = parse_product_page(_markup({"@type": "Product", "name": "Кабель ABC", "description": "Остаток: 3 м. Минимальный заказ: 5 м.", "offers": {
        "inventoryLevel": {"value": 50, "unitCode": "MTR"}, "eligibleQuantity": {"minValue": 10, "unitCode": "MTR"},
    }}, "Кабель ABC"), "https://shop.example.kz/p/cable")
    assert page["stock_quantity"] is None
    assert page["min_order_quantity"] is None


def test_negated_own_stock_text_cannot_confirm_quantity_or_override_outofstock():
    page = parse_product_page(_markup({"@type": "Product", "name": "Кабель ABC", "description": "Нет в наличии: 20 шт.", "offers": {"availability": "https://schema.org/InStock"}}, "Кабель ABC"), "https://shop.example.kz/p/cable")
    assert page["stock_quantity"] is None
    assert page["availability"] == "OutOfStock"
    known = parse_product_page(_markup({"@type": "Product", "name": "Кабель ABC", "description": "Нет в наличии", "offers": {"availability": "https://schema.org/InStock", "inventoryLevel": {"value": 100, "unitCode": "H87"}}}, "Кабель ABC"), "https://shop.example.kz/p/cable")
    assert known["availability"] == "OutOfStock"


def test_price_basis_requires_its_own_unit_price_publication():
    page = parse_product_page(_markup({"@type": "Product", "name": "Материал ABC", "offers": {
        "price": "2500", "priceCurrency": "KZT", "priceSpecification": {"@type": "UnitPriceSpecification", "price": 2500,
          "priceCurrency": "KZT", "referenceQuantity": {"value": "2.5", "unitCode": "KGM"}},
    }}, "Материал ABC"), "https://shop.example.kz/p/material")
    assert (page["price_quantity"], page["price_unit"], page["price_basis_status"]) == (2.5, "кг", "published")
    unknown = parse_product_page(_markup({"@type": "Product", "name": "Материал ABC", "offers": {"price": 2500, "priceCurrency": "KZT"}}, "Материал ABC"), "https://shop.example.kz/p/material")
    assert unknown["price_quantity"] is None
    assert unknown["price_unit"] is None
    assert unknown["price_basis_status"] == "unknown"


@pytest.mark.parametrize("visible,expected", [("2500 ₸/шт", (1, "шт", "published")), ("2500 ₸ за 100 мл", (100, "мл", "published")), ("2500 ₸", (None, None, "unknown"))])
def test_only_scoped_explicit_visible_price_basis_is_used(visible, expected):
    markup = f'<title>Товар ABC</title><p class="price">1 ₸/шт</p><div class="product type-product"><h1 class="product_title">Товар ABC</h1><p class="price">{visible}</p><section class="related"><p class="price">2500 ₸/кг</p></section></div>'
    page = parse_product_page(markup, "https://shop.example.kz/p/item")
    assert (page["price_quantity"], page["price_unit"], page["price_basis_status"]) == expected


def _variant_product():
    return {"@type": "Product", "name": "Товар ABC", "description": "В наличии: 999 шт. Минимальный заказ: 1 шт. Оптовая цена.", "offers": [
        {"url": "https://shop.example.kz/p/item?size=S", "sku": "SKU-S", "price": 1000, "priceCurrency": "KZT", "availability": "https://schema.org/InStock", "inventoryLevel": {"value": 100, "unitCode": "H87"}},
        {"url": "https://shop.example.kz/p/item?size=M", "sku": "SKU-M", "price": 2000, "priceCurrency": "KZT", "availability": "https://schema.org/OutOfStock", "inventoryLevel": {"value": 0, "unitCode": "H87"}},
    ]}


def test_exact_variant_url_keeps_price_and_stock_from_the_same_offer():
    page = parse_product_page(_markup(_variant_product(), "Товар ABC"), "https://shop.example.kz/p/item?size=M")
    assert page["variant_status"] == "selected"
    assert (page["price"], page["availability"], page["stock_quantity"], page["product_sku"]) == (2000, "OutOfStock", 0, "SKU-M")
    assert page["min_order_quantity"] is None
    assert page["wholesale_terms"] is None


def test_unique_published_sku_can_select_offer_but_conflicting_url_cannot():
    product = _variant_product()
    product["sku"] = "SKU-M"
    selected = parse_product_page(_markup(product, "Товар ABC"), "https://shop.example.kz/p/item")
    assert selected["variant_status"] == "selected"
    assert selected["price"] == 2000
    conflicting = parse_product_page(_markup(product, "Товар ABC"), "https://shop.example.kz/p/item?size=S")
    assert conflicting["variant_status"] == "ambiguous"
    assert conflicting["price"] is None


@pytest.mark.parametrize("as_list,sku_field", [(False, {"sku": "SOAP750"}), (True, {"itemOffered": {"sku": "SOAP750"}})])
def test_single_offer_with_conflicting_main_sku_cannot_supply_commercial_fields(as_list, sku_field):
    offer = {**sku_field, "price": 1250, "priceCurrency": "KZT", "availability": "https://schema.org/InStock", "inventoryLevel": {"value": 24, "unitCode": "H87"}, "eligibleQuantity": {"minValue": 5, "unitCode": "H87"}}
    product = {"@type": "Product", "name": "Мыло жидкое 500 мл", "sku": "SOAP500", "description": "Оптовая цена.", "offers": [offer] if as_list else offer}
    page = parse_product_page(_markup(product, "Мыло жидкое 500 мл"), "https://shop.example.kz/p/soap500")
    assert page["variant_status"] == "ambiguous"
    assert page["product_sku"] is None
    for field in ("price", "currency", "stock_quantity", "stock_unit", "min_order_quantity", "min_order_unit", "availability", "wholesale_terms"):
        assert page[field] is None, field


def test_single_offer_cannot_override_visible_sku_or_explicit_selected_variant_url():
    product = {"@type": "Product", "name": "Товар ABC", "offers": {"sku": "SKU-S", "url": "https://shop.example.kz/p/item?size=S", "price": 1000}}
    visible = _markup(product, "Товар ABC").replace("</body>", '<div class="product type-product"><h1 class="product_title">Товар ABC</h1><span class="sku">SKU-M</span></div></body>')
    assert parse_product_page(visible, "https://shop.example.kz/p/item")["variant_status"] == "ambiguous"
    assert parse_product_page(_markup(product, "Товар ABC"), "https://shop.example.kz/p/item?size=M")["variant_status"] == "ambiguous"
    product["offers"]["url"] = "https://merchant.example.com/checkout?size=S"
    product["sku"] = "SKU-S"
    assert parse_product_page(_markup(product, "Товар ABC"), "https://shop.example.kz/p/item")["variant_status"] == "single"


def test_ambiguous_variants_cannot_refill_commercial_data_from_shared_meta_or_dom():
    markup = _markup(_variant_product(), "Товар ABC").replace("</head>", '<meta property="product:price:amount" content="123"><meta property="product:price:currency" content="KZT"></head>').replace("</body>", '''
      <div class="product type-product instock"><h1 class="product_title">Товар ABC</h1>
        <p class="price">123 ₸/шт</p><p class="stock">В наличии: 500 шт</p>
      </div></body>''')
    page = parse_product_page(markup, "https://shop.example.kz/p/item")
    assert page["variant_status"] == "ambiguous"
    for field in ("price", "currency", "stock_quantity", "stock_unit", "stock_evidence", "availability", "min_order_quantity", "min_order_unit", "price_quantity", "price_unit", "wholesale_terms"):
        assert page[field] is None, field
    assert page["price_basis_status"] == "unknown"


def test_aggregate_lowest_price_and_nested_family_variants_are_not_selected_offers():
    for extra in ({"offers": {"@type": "AggregateOffer", "lowPrice": 1000, "highPrice": 5000, "priceCurrency": "KZT"}},
                  {"hasVariant": [{"@type": "Product", "name": "Товар ABC M", "url": "https://shop.example.kz/p/item?size=M", "offers": {"price": 5000}}]}):
        page = parse_product_page(_markup({"@type": "Product", "name": "Товар ABC", **extra}, "Товар ABC"), "https://shop.example.kz/p/item?size=M")
        assert page["variant_status"] == "ambiguous"
        assert page["price"] is None


def test_unresolved_visible_variant_selector_cannot_turn_default_offer_into_single_variant():
    markup = _markup({"@type": "Product", "name": "Товар ABC", "offers": {"price": 1000, "availability": "https://schema.org/InStock"}}, "Товар ABC").replace("</body>", '<div class="product type-product"><h1 class="product_title">Товар ABC</h1><form class="variations_form"><select name="attribute_size"><option>S</option><option>M</option></select></form></div></body>')
    page = parse_product_page(markup, "https://shop.example.kz/p/item")
    assert page["variant_status"] == "ambiguous"
    assert page["price"] is None
    assert page["availability"] is None


def test_product_certificate_links_are_scoped_unverified_and_never_proof_from_flags():
    markup = _markup({"@type": "Product", "name": "Товар ABC", "certificate_status": "verified"}, "Товар ABC").replace("</body>", '''
      <nav><a href="/nav.pdf">Сертификат</a></nav><h1>Товар ABC</h1>
      <div class="product-description"><h3>Сертификаты</h3><a href="/docs/cert.pdf">ГОСТ 25295-2003</a>
        <a href="/docs/cert.pdf">Сертификат</a><a href="#cert">Сертификат</a>
        <a href="http://127.0.0.1/private.pdf">Сертификат</a><a href="javascript:alert(1)">Сертификат</a>
        <h3>Доставка и возврат</h3><a href="/delivery.pdf">Сертификат другого товара</a>
        <section id="recommendations"><a href="/other.pdf">Сертификат</a></section>
      </div><footer><a href="/footer.pdf">Сертификат</a></footer></body>''')
    page = parse_product_page(markup, "https://shop.example.kz/p/item")
    assert page["certificate_status"] == "document_linked"
    assert page["certificate_documents"] == [{"url": "https://shop.example.kz/docs/cert.pdf", "label": "ГОСТ 25295-2003", "status": "unverified"}]


@pytest.mark.parametrize("description,expected", [("Соответствует ГОСТ 25295-2003", "claim_only"), ("Нет сертификата ГОСТ 25295-2003", "missing"), ("Товар ABC", "missing")])
def test_plain_standard_or_page_claim_never_verifies_certificate(description, expected):
    page = parse_product_page(_markup({"@type": "Product", "name": "Товар ABC", "description": description, "verified": True}, "Товар ABC"), "https://shop.example.kz/p/item")
    assert page["certificate_status"] == expected
    assert page["certificate_documents"] == []


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


def test_satu_numbered_product_path_is_a_product_card():
    page = parse_product_page(
        _markup(
            {
                "@type": "Product",
                "name": "Ветрозащита для микрофона поролоновая",
                "image": "https://images.example.kz/microphone-windscreen.jpg",
            },
            "Ветрозащита для микрофона поролоновая",
        ),
        "https://satu.kz/p132004766-vetrozaschita-mikrofon.html",
    )
    assert page["is_product_page"] is True
    assert looks_like_product_url("https://satu.kz/p132004766-vetrozaschita-mikrofon.html")


def test_satu_search_extracts_unique_concrete_product_pages():
    rows = _satu_product_results(
        '<a href="/p123505677-pylesos-philips-fc973401.html">Товар</a>'
        '<a href="https://satu.kz/p123505677-pylesos-philips-fc973401.html?x=1">Дубликат</a>'
        '<a href="/search?search_term=philips">Поиск</a>'
    )
    assert [row["url"] for row in rows] == [
        "https://satu.kz/p123505677-pylesos-philips-fc973401.html"
    ]


def test_product_page_extracts_published_seller_and_phone():
    markup = _markup(
        {
            "@type": "Product",
            "name": "Пылесос Philips FC9734/01",
            "offers": {
                "price": "178490",
                "priceCurrency": "KZT",
                "seller": {"@type": "Organization", "name": "ТОО Elektrica Trade"},
            },
        },
        "Пылесос Philips FC9734/01",
    ).replace("</body>", 'PhoneDescription:+7 (700) 507-40-50</body>')
    page = parse_product_page(markup, "https://satu.kz/p123505677-pylesos-philips-fc973401.html")
    assert page["seller_name"] == "ТОО Elektrica Trade"
    assert page["seller_phone"] == "+7 (700) 507-40-50"
    assert page["seller_phones"] == ["+7 (700) 507-40-50"]


@pytest.mark.asyncio
async def test_unreadable_direct_product_url_remains_an_unverified_candidate(monkeypatch):
    async def blocked_page(*_args, **_kwargs):
        return {"is_product_page": False, "page_verified": False}

    monkeypatch.setattr("app.services.market_search.fetch_product_page", blocked_page)
    rows = await enrich_product_pages([
        {
            "title": "Ветрозащита для микрофона",
            "url": "https://satu.kz/p132004766-vetrozaschita-mikrofon.html",
            "price": 1234,
            "image_url": "https://images.example.kz/unverified.jpg",
        }
    ])

    assert rows[0]["is_product_page"] is True
    assert rows[0]["page_verified"] is False
    assert rows[0]["price"] is None
    assert rows[0]["image_url"] is None


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
async def test_unpublished_certificate_stays_unknown_without_ai_request(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "GOOGLE_AI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    client = Mock(side_effect=AssertionError("Product matching must not request an AI provider"))
    monkeypatch.setattr(httpx, "AsyncClient", client)
    leads = await evaluate_product_leads(
        "Моющее средство для посуды, 500 мл",
        "ГОСТ Р 51696-2003",
        [{"url": "https://shop.example.kz/p/2", "is_product_page": True, "page_verified": True,
          "evidence_text": "Моющее средство для посуды 500 мл"}],
    )
    assert leads[0]["match_status"] == "partial"
    assert leads[0]["checks"][-1]["status"] == "unknown"
    client.assert_not_called()


@pytest.mark.asyncio
async def test_percentage_without_named_ingredient_stays_unknown_without_ai_request(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "GOOGLE_AI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    client = Mock(side_effect=AssertionError("Product matching must not request an AI provider"))
    monkeypatch.setattr(httpx, "AsyncClient", client)
    leads = await evaluate_product_leads(
        "Моющее средство для туалета, 500 мл",
        "н-ПАВ больше 5%",
        [{"url": "https://shop.example.kz/p/4", "is_product_page": True, "page_verified": True,
          "evidence_text": "Моющее средство для туалета 500 мл\nСостав: 5% очищенная вода"}],
    )
    assert leads[0]["checks"][-1]["status"] == "unknown"
    client.assert_not_called()
