
from app.services.product_extraction import extract_products_from_text
from app.services.market_search import _extract_price, _shop_from_url, _relevant_result
from app.tasks.product_search_tasks import _build_search_query, _region_of


SPEC_TEXT = """
## Спецификация элементов крыши

| № | Наименование | Характеристика | Ед. изм. | Кол-во |
|---|---|---|---|---|
| 1 | Металлочерепица | МП Супермонтеррей, 0,5 мм | м2 | 789,1 |
| 2 | Доска обрезная | 25х150 мм, сорт 1 | м3 | 8,95 |
| 3 | Утеплитель базальтовый | плотность 100 кг/м3 | м3 | 12 |

Ведомость демонтажных работ
| 1 | Разборка кровельного покрытия | асбестоцементные листы | м2 | 789,1 |
"""


def test_extract_products_from_table_rows():
    products = extract_products_from_text(SPEC_TEXT)
    names = [p["product_name"] for p in products]

    assert "Металлочерепица" in names
    assert "Доска обрезная" in names
    assert "Утеплитель базальтовый" in names

    by_name = {p["product_name"]: p for p in products}
    assert by_name["Металлочерепица"]["unit"] == "м2"
    assert by_name["Металлочерепица"]["quantity"] == 789.1
    assert by_name["Доска обрезная"]["unit"] == "м3"
    assert by_name["Доска обрезная"]["quantity"] == 8.95
    assert by_name["Доска обрезная"]["specs"] is not None


def test_extract_products_no_duplicates():
    products = extract_products_from_text(SPEC_TEXT + SPEC_TEXT)
    names = [p["product_name"] for p in products]
    assert len(names) == len(set(names))


def test_extract_products_plain_lines():
    text = (
        "Требования к материалам:\n"
        "Металлочерепица МП Супермонтеррей 0,5 мм 789 м2\n"
        "Бетон М300 150 м3\n"
    )
    products = extract_products_from_text(text)
    names = [p["product_name"] for p in products]
    assert len(products) >= 1


def test_extract_products_from_bilingual_kazakhstan_techspec():
    text = """
Лоттың нөмірі : 84683164
Лоттың қысқаша сипаттауы: Ыдысқа арналған жуу құралы (сұйық)
Саны, көлемі: 62
Өлшем бірлігі: Дана
Номер пункта плана: № 84683164
Наименование пункта плана: Cредство моющее
Описание пункта плана: для мытья посуды, жидкость
Дополнительное описание
пункта плана:
Моющее средство для посуды, жидкое, 500 мл
Количество: 62
Единица измерения: Штука
Места поставки: г. Риддер, ул. Бухмейера, 9
Срок поставки: 15 рабочих дней
Описание требуемых функциональных, технических, качественных,
эксплуатационных и иных характеристик закупаемого
товара:
Моющее средство для посуды (жидкое), объем 500 мл СТ РК ГОСТ Р 51696-2003
Номер пункта плана: № 84742597
Дополнительное описание пункта плана: Моющее средство для туалета, 500 гр
Количество: 120
Единица измерения: Штука
"""
    products = extract_products_from_text(text)

    assert len(products) == 2
    assert products[0]["product_name"] == "Моющее средство для посуды, жидкое, 500 мл"
    assert products[0]["quantity"] == 62
    assert products[0]["unit"] == "Штука"
    assert "Бухмейера" in products[0]["specs"]
    assert products[1]["quantity"] == 120


def test_search_query_is_bounded_but_keeps_name():
    query = _build_search_query("Моющее средство 500 мл", "Х" * 500)
    assert query.startswith("Моющее средство 500 мл")
    assert len(query) <= 120


def test_search_query_uses_package_size_instead_of_long_tender_prose():
    query = _build_search_query(
        "Моющее средство для туалета, 500 гр",
        "Удаляет ржавчину. Объём 500 мл, состав: вода; Место поставки: г. Риддер",
    )
    assert query == "Моющее средство для туалета 500 мл"


def test_search_query_prefers_brand_and_model_hidden_in_tender_prose():
    query = _build_search_query(
        "Шаңсорғыш жууға арналған Лоттың қысқаша сипаттауы:",
        "Характеристики пылесоса Philips FC9734/01. Мощность 2100 Вт.",
    )
    assert query == "Philips FC9734/01"


def test_extract_price_tenge():
    assert _extract_price("Цена: 25 000 тенге") == 25000.0
    assert _extract_price("25 000 ₸") == 25000.0
    assert _extract_price("12 500 тг") == 12500.0
    assert _extract_price("1 250 000 тенге") == 1250000.0
    assert _extract_price("нет цены") is None


def test_extract_price_loose():
    assert _extract_price("Бетон М300 с доставкой от 18 000") == 18000.0
    assert _extract_price("Цена 17 000 ₸/м3") == 17000.0
    assert _extract_price("стоимость ~ 1 500") == 1500.0
    assert _extract_price("В наличии 5 шт") is None
    assert _extract_price("от 99") is None


def test_shop_from_url():
    assert _shop_from_url("https://kaspi.kz/shop/p/123") == "kaspi.kz"
    assert _shop_from_url("https://www.satu.kz/items/1") == "satu.kz"
    assert _shop_from_url(None) is None


def test_relevant_result():
    match = {"title": "Купить Бетон М300 в Алматы", "url": "https://zavod-beton.kz/beton/m300"}
    assert _relevant_result(match, "Бетон М300") is True
    assert _relevant_result({"title": "Новости стройки", "url": "https://news.kz/1"}, "Бетон М300") is False
    assert _relevant_result({"title": "М300", "url": "https://example.com/"}, "Бетон М300") is False


def test_region_of():
    class C:
        actual_address = "050000, г. Алматы, ул. Абая, 10"
        legal_address = None
    assert _region_of(C()) == "г. Алматы"

    class C2:
        actual_address = "Алматы облысы, г. Талдыкорган"
        legal_address = None
    assert _region_of(C2()) == "Алматы облысы"

    class C3:
        actual_address = None
        legal_address = None
    assert _region_of(C3()) is None
