"""Regression coverage for real procurement label layouts and Word tables."""

from pathlib import Path

import pytest

from app.core.parsers import DocumentParser
from app.services.product_extraction import extract_products_from_text


GOSZAKUP_SPEC = Path(__file__).parents[1] / "fixtures" / "goszakup_lot_spec.txt"


def test_goszakup_lot_pdf_layout_preserves_quantity_and_prefers_russian():
    # Redacted layout from a public procurement PDF. The PDF text extractor
    # emits quantity on its own line and wraps table field labels.
    text = DocumentParser.clean_text(GOSZAKUP_SPEC.read_text())
    products = extract_products_from_text(text)

    assert len(products) == 1
    assert products[0]["product_name"] == "Жакет женский на замке из плотной вязки"
    assert products[0]["quantity"] == 20
    assert products[0]["unit"] == "Штука"
    assert products[0]["source_section"] == "Лот № 80000001-ОИ2"
    assert "ГОСТ 25295-2003" in products[0]["specs"]
    assert "Место поставки: Тестовый город" in products[0]["specs"]


def test_kazakh_only_lot_retains_wrapped_requirements():
    text = GOSZAKUP_SPEC.read_text().split("Приложение 2")[0]
    products = extract_products_from_text(DocumentParser.clean_text(text))

    assert len(products) == 1
    assert products[0]["quantity"] == 20
    assert products[0]["product_name"] == "Тығыз тоқылған құлыптағы әйел жакет"
    assert "Жүннен жасалған" in products[0]["specs"]


def test_docx_label_value_cells_and_nonbreaking_quantity_spaces():
    text = """Номер лота: | № 80000001-ОИ2
Наименование лота | Жакет
Дополнительное описание лота | Жакет женский шерстяной
Количество | 1\u202f200,5
Единица измерения | Штука
Описание и требуемые функциональные, технические, качественные и эксплуатационные характеристики закупаемых товаров | Рукав длинный
"""
    products = extract_products_from_text(text)

    assert len(products) == 1
    assert products[0]["quantity"] == 1200.5
    assert products[0]["unit"] == "Штука"
    assert products[0]["specs"] == "Рукав длинный"


@pytest.mark.parametrize("row", [
    "Средство для посуды | 12 шт",
    "1 | Средство для посуды | 12 шт",
    "Средство для посуды | 12 | Штука",
    "Средство для посуды | Штука | 12",
    "Средство для посуды | Жидкое | шт | 12",
    "1 | Средство для посуды | Жидкое | шт | 12",
])
def test_common_word_table_rows_have_real_quantities(row):
    products = extract_products_from_text(row)

    assert len(products) == 1
    assert products[0]["product_name"] == "Средство для посуды"
    assert products[0]["quantity"] == 12
    assert products[0]["unit"] in {"шт", "Штука"}


@pytest.mark.parametrize("row", ["Жакет женский | 25 000 тенге", "Жакет женский | 25 000 | тенге"])
def test_price_only_word_table_is_not_a_quantity(row):
    assert extract_products_from_text(row) == []


def test_invalid_labeled_quantity_does_not_create_an_unusable_product():
    assert extract_products_from_text("""Номер лота: 80000001-ОИ2
Наименование лота: Жакет
Количество: согласно заявке
Единица измерения: Штука""") == []


def test_explicit_trailing_requirements_belong_to_only_table_product():
    products = extract_products_from_text("""Наименование | Количество | Единица
Пылесос Philips FC9734/01 | 20 | шт

Требуемые характеристики: мощность 2100 Вт, объём пылесборника 2 л.
""")

    assert len(products) == 1
    assert products[0]["specs"] == "мощность 2100 Вт, объём пылесборника 2 л."


def test_shared_requirements_are_not_assigned_to_multiple_table_products():
    products = extract_products_from_text("""Пылесос Philips FC9734/01 | 20 | шт
Пылесос Bosch BGL | 10 | шт

Требуемые характеристики: мощность 2100 Вт, объём пылесборника 2 л.
""")

    assert len(products) == 2
    assert all(product["specs"] is None for product in products)


@pytest.mark.parametrize("paragraph", [
    "Цены, остатки и контакты должны быть проверены по открытым страницам магазинов.",
    "Требуемые характеристики: Контакт продавца: +7 700 000 00 00.",
    "Технические требования: Цена 25 000 тенге.",
    "Условия поставки: 30 дней.",
])
def test_commercial_or_unlabeled_trailing_text_is_not_product_requirements(paragraph):
    products = extract_products_from_text(f"Пылесос Philips FC9734/01 | 20 | шт\n\n{paragraph}")

    assert len(products) == 1
    assert products[0]["specs"] is None


def test_requirements_stop_at_commercial_instructions_and_next_section():
    products = extract_products_from_text("""Пылесос Philips FC9734/01 | 20 | шт

Требуемые характеристики: мощность 2100 Вт, объём пылесборника 2 л. Цены, остатки и контакты должны быть проверены по открытым страницам магазинов.

Контакты: +7 700 000 00 00
""")

    assert products[0]["specs"] == "мощность 2100 Вт, объём пылесборника 2 л."
