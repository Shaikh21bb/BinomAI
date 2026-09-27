import csv
import io

from app.services.sourcing_csv import (
    build_sourcing_export,
    build_supplier_import_template,
)


def read_rows(content: str):
    return list(csv.DictReader(io.StringIO(content.lstrip("\ufeff")), delimiter=";"))


def test_import_template_prefills_tender_items():
    content = build_supplier_import_template(
        [
            {
                "id": "item-1",
                "product_name": "Цемент М500",
                "quantity": 25,
                "unit": "кг",
                "required_certificates": ["СТ-KZ", "паспорт качества"],
            }
        ]
    )

    rows = read_rows(content)
    assert content.startswith("\ufeff")
    assert rows[0]["item_id"] == "item-1"
    assert rows[0]["Наименование"] == "Цемент М500"
    assert rows[0]["Количество"] == "25"
    assert rows[0]["Сертификаты"] == "СТ-KZ; паспорт качества"


def test_comparison_export_marks_effective_offer_and_blocks_formula_injection():
    content = build_sourcing_export(
        {
            "items": [
                {
                    "id": "item-1",
                    "product_name": "Кабель",
                    "quantity": 100,
                    "unit": "м",
                    "effective_offer_id": "offer-1",
                    "offers": [
                        {
                            "id": "offer-1",
                            "supplier_name": "=HYPERLINK(\"https://example.test\")",
                            "product_name": "Кабель ВВГ",
                            "unit_price": "125.50",
                            "currency": "KZT",
                            "match_status": "confirmed",
                            "source_type": "manual",
                            "is_selected": False,
                            "is_recommended": True,
                            "calculation": {
                                "landed_cost_kzt": "12550.00",
                                "score": "93",
                                "eligible": True,
                                "risks": [
                                    {"code": "vat_unknown", "message": "НДС не указан"}
                                ],
                            },
                        }
                    ],
                }
            ],
            "unmatched_offers": [],
        }
    )

    rows = read_rows(content)
    assert rows[0]["Поставщик"].startswith("'=")
    assert rows[0]["Итоговый выбор"] == "да"
    assert rows[0]["Рекомендуется"] == "да"
    assert rows[0]["Коды рисков"] == "vat_unknown"
