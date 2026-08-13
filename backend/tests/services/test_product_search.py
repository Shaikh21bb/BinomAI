import pytest

from app.services.product_extraction import extract_products_from_text
from app.services.market_search import _extract_price, _shop_from_url, _relevant_result, _enrich_images
from app.tasks.product_search_tasks import _region_of


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


async def test_enrich_images_og_image(mocker):
    results = [
        {"url": "https://satu.kz/item/1", "title": "x", "image_url": None},
        {"url": "https://zavod-beton.kz/2", "title": "y", "image_url": None},
    ]
    html = '<html><head><meta property="og:image" content="https://cdn.example.com/img.jpg"></head></html>'

    class FakeResp:
        def __init__(self, text):
            self.status_code = 200
            self.text = text

    mock_client = mocker.patch("app.services.market_search.httpx.AsyncClient")
    mock_client.return_value.__aenter__.return_value.get.side_effect = [
        FakeResp(html),
        FakeResp("<html><body>no image here</body></html>"),
    ]

    out = await _enrich_images(results)
    assert out[0]["image_url"] == "https://cdn.example.com/img.jpg"
    assert "favicons" in out[1]["image_url"]  # favicon fallback


async def test_enrich_images_respects_limit(mocker):
    results = [
        {"url": f"https://shop{i}.kz/p", "title": "t", "image_url": None}
        for i in range(10)
    ]
    mock_client = mocker.patch("app.services.market_search.httpx.AsyncClient")
    mock_client.return_value.__aenter__.return_value.get.side_effect = Exception("timeout")
    out = await _enrich_images(results, limit=3)
    assert all(r["image_url"] for r in out[:3])
    assert not out[3]["image_url"]
    assert mock_client.return_value.__aenter__.return_value.get.call_count == 3


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
