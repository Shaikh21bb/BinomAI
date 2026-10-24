"""Focused requirement and evidence regressions from the live PDF/Word checks."""

from unittest.mock import Mock

import httpx
import pytest

from app.core.config import settings
from app.services.product_matching import _compare_locally, _requirements, _type_check, evaluate_product_leads


JACKET_NAME = "Жакет женский на замке из плотной вязки"
JACKET_SPECS = (
    "Жакет женский шерстяной. Горловина разная: круглая, V образная, в воротником. "
    "Цвет разный, однотонный. Рукав длинный. Карман — да; "
    "Застежка — молния, пуговица, можно без застежки некоторые модели; стиль — пиджачный. "
    "ГОСТ 25295-2003 ПЕРЕД ПОСТАВКОЙ ОБЯЗАТЕЛЬНО ТОВАР СОГЛАСОВАТЬ С ЗАКАЗЧИКОМ!! "
    "РАЗМЕРЫ И ДРУГИЕ ХАРАКТЕРИСТИКИ Погрузка, поставка, разгрузка товара осуществляется "
    "Поставщиком самостоятельно до места назначения Заказчика и входит в стоимость закупки. "
    "Уважаемый поставщик, просим вас доставить качественный товар. Без согласования товар не принимается!!!; "
    "Место поставки: Тестовый город; Срок поставки: 30 календарных дней"
)


@pytest.fixture(autouse=True)
def no_paid_matching(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_AI_API_KEY", None)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)


@pytest.fixture
def configured_ai_without_requests(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_AI_API_KEY", "configured-but-not-used")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "configured-but-not-used")
    client = Mock(side_effect=AssertionError("Product matching must not request an AI provider"))
    monkeypatch.setattr(httpx, "AsyncClient", client)
    yield
    client.assert_not_called()


def test_procurement_jacket_keeps_product_requirements_not_buyer_instructions():
    requirements = _requirements(JACKET_NAME, JACKET_SPECS)
    texts = [requirement["text"] for requirement in requirements]

    assert "ГОСТ 25295-2003" in texts
    assert "Застежка: молния" in texts
    assert "Плотная вязка" in texts
    assert any("круглая, V образная" in text for text in texts)
    assert not any(any(word in text.casefold() for word in (
        "заказчик", "поставщик", "погруз", "разгруз", "согласова", "тестовый город", "30 календарных", "уважаемый",
    )) for text in texts)
    assert len(requirements) < 15


@pytest.mark.parametrize("evidence,expected", [
    ("Жакет женский\nМатериал: шерсть", "matched"),
    ("Жакет\nПол: женский\nРукав: длинный", "matched"),
    ("Жакет мужской\nМатериал: шерсть", "mismatch"),
    ("Куртка женская\nМатериал: шерсть", "mismatch"),
    ("Жакет\nМатериал: шерсть", "unknown"),
])
def test_jacket_type_uses_category_and_gender_not_every_name_adjective(evidence, expected):
    assert _type_check(JACKET_NAME, evidence)["status"] == expected


@pytest.mark.parametrize("requirement,evidence,expected", [
    ("мощность 2100 Вт", "Потребляемая мощность: 2,1 кВт", "matched"),
    ("мощность 2100 Вт", "Потребляемая мощность: 2000 Вт", "mismatch"),
    ("мощность не менее 2100 Вт", "Потребляемая мощность: 2200 Вт", "matched"),
    ("мощность не менее 2100 Вт", "Потребляемая мощность: 2000 Вт", "mismatch"),
    ("мощность всасывания 470 Вт", "Потребляемая мощность: 2100 Вт", "unknown"),
    ("мощность всасывания 470 Вт", "Потребляемая мощность: 2100 Вт, Мощность всасывания: 400 Вт", "mismatch"),
    ("объём пылесборника 2 л", "Объем пылесборника: 2000 мл", "matched"),
    ("объём пылесборника 2 л", "Объем пылесборника: 3 л", "mismatch"),
    ("объём пылесборника 2 л", "Объем резервуара для воды: 2 л", "unknown"),
    ("100% шерсть", "Состав: шерсть", "unknown"),
    ("Материал: шерсть", "Состав: 100% хлопок", "mismatch"),
    ("Материал: шерсть", "Материал: без шерсти", "mismatch"),
    ("Материал: шерсть", "Материал: шерсть отсутствует", "mismatch"),
    ("Застежка: молния", "Застежка: пуговицы", "mismatch"),
    ("ГОСТ 25295-2003", "Сертификат имеется", "unknown"),
    ("ГОСТ 25295-2003", "Не соответствует ГОСТ 25295-2003", "mismatch"),
    ("ГОСТ 25295-2003", "Соответствует ГОСТ 25295-2003", "matched"),
])
def test_numeric_material_closure_and_standard_claims_need_their_own_evidence(requirement, evidence, expected):
    assert _compare_locally(requirement, evidence)["status"] == expected


def _lead(url: str, evidence: str, availability: str = "InStock"):
    return {"url": url, "is_product_page": True, "page_verified": True,
            "evidence_text": evidence, "availability": availability}


@pytest.mark.asyncio
async def test_real_word_power_and_dust_capacity_are_both_checked():
    leads = await evaluate_product_leads(
        "Пылесос Philips FC9734/01", "мощность 2100 Вт, объём пылесборника 2 л.",
        [_lead("https://shop.example.kz/p/vacuum", "Пылесос Philips FC9734/01\nПотребляемая мощность: 2100 Вт\nОбъем пылесборника: 2 л")],
    )

    assert len(leads[0]["checks"]) == 3
    assert leads[0]["match_status"] == "matched"
    assert all(check["evidence"] for check in leads[0]["checks"])


@pytest.mark.asyncio
async def test_appropriate_jacket_is_partial_when_standard_and_details_unproven():
    leads = await evaluate_product_leads(
        JACKET_NAME, JACKET_SPECS,
        [_lead("https://shop.example.kz/p/jacket", "Жакет женский\nПлотная вязка\nЗастежка: молния\nРукав: длинный\nСостав: шерсть")],
    )

    assert leads[0]["checks"][0]["status"] == "matched"
    assert leads[0]["match_status"] == "partial"
    assert next(check for check in leads[0]["checks"] if check["requirement"] == "ГОСТ 25295-2003")["status"] == "unknown"


@pytest.mark.asyncio
async def test_stock_state_ranks_equal_matches_without_changing_compliance():
    leads = await evaluate_product_leads(
        "Пылесос Philips FC9734/01", "мощность 2100 Вт",
        [_lead("https://shop.example.kz/p/sold-out", "Пылесос Philips FC9734/01\nМощность: 2100 Вт", "OutOfStock"),
         _lead("https://shop.example.kz/p/in-stock", "Пылесос Philips FC9734/01\nМощность: 2100 Вт", "InStock")],
    )

    assert leads[0]["availability"] == "InStock"
    assert all(lead["match_status"] == "matched" for lead in leads)
    assert all("stock_quantity" not in lead and "price" not in lead and "seller_phone" not in lead for lead in leads)


@pytest.mark.asyncio
async def test_in_stock_partial_ranks_before_sold_out_partial_with_more_checked_details():
    leads = await evaluate_product_leads(
        "Пылесос Philips FC9734/01", "мощность 2100 Вт, объём пылесборника 2 л; ГОСТ 25295-2003",
        [_lead("https://shop.example.kz/p/sold-out", "Пылесос Philips FC9734/01\nМощность: 2100 Вт\nОбъем пылесборника: 2 л", "OutOfStock"),
         _lead("https://shop.example.kz/p/in-stock", "Пылесос Philips FC9734/01\nМощность: 2100 Вт", "InStock")],
    )

    assert all(lead["match_status"] == "partial" for lead in leads)
    assert leads[0]["availability"] == "InStock"
    assert sum(check["status"] == "matched" for check in leads[0]["checks"]) < sum(check["status"] == "matched" for check in leads[1]["checks"])


@pytest.mark.asyncio
async def test_configured_ai_cannot_fill_missing_requirements_or_request_provider(configured_ai_without_requests):
    leads = await evaluate_product_leads(
        JACKET_NAME, "100% шерсть; ГОСТ 25295-2003",
        [_lead("https://shop.example.kz/p/jacket", "Жакет женский")],
    )

    assert leads[0]["match_status"] == "partial"
    assert all(check["status"] == "unknown" for check in leads[0]["checks"][1:])


@pytest.mark.asyncio
@pytest.mark.parametrize("requirement,evidence,quote", [
    ("ГОСТ 25295-2003", "Нет сертификата ГОСТ 25295-2003", "ГОСТ 25295-2003"),
    ("ГОСТ 25295-2003", "ГОСТ 25295-2003: сертификат отсутствует", "ГОСТ 25295-2003"),
    ("Рукав длинный", "Рукав: длинный\nРукав: короткий", "Рукав: длинный"),
    ("100% шерсть", "Состав: 100% шерсть\nСостав: 10% шерсть", "Состав: 100% шерсть"),
    ("мощность всасывания 470 Вт", "Мощность всасывания: 470 Вт / 400 Вт", "Мощность всасывания: 470 Вт"),
])
async def test_configured_ai_cannot_cherry_pick_positive_quote_from_unproven_full_source(configured_ai_without_requests, requirement, evidence, quote):
    assert _compare_locally(requirement, evidence)["status"] == "unknown"
    assert _compare_locally(requirement, quote)["status"] == "matched"

    leads = await evaluate_product_leads(
        "Жакет женский", requirement,
        [_lead("https://shop.example.kz/p/jacket", f"Жакет женский\n{evidence}")],
    )

    check = next(check for check in leads[0]["checks"] if check["requirement"] == requirement)
    assert check["status"] == "unknown"
    assert not check["evidence"]
    assert leads[0]["match_status"] == "partial"


@pytest.mark.asyncio
@pytest.mark.parametrize("additional_requirement,expected", [("", "matched"), ("; Рукав длинный", "partial")])
async def test_complete_positive_evidence_remains_confirmed_with_ai_enabled(configured_ai_without_requests, additional_requirement, expected):
    leads = await evaluate_product_leads(
        "Жакет женский", f"ГОСТ 25295-2003{additional_requirement}",
        [_lead("https://shop.example.kz/p/jacket", "Жакет женский\nСоответствует ГОСТ 25295-2003")],
    )

    assert next(check for check in leads[0]["checks"] if "ГОСТ" in check["requirement"])["status"] == "matched"
    if additional_requirement:
        assert next(check for check in leads[0]["checks"] if check["requirement"] == "Рукав длинный")["status"] == "unknown"
    assert leads[0]["match_status"] == expected


@pytest.mark.parametrize("evidence,expected", [
    ("Мощность всасывания: 400 Вт / потребляемая мощность: 470 Вт", "mismatch"),
    ("Мощность всасывания: 400 Вт | потребляемая мощность: 470 Вт", "mismatch"),
    ("Мощность всасывания: 400 Вт; потребляемая мощность: 470 Вт", "mismatch"),
    ("Мощность всасывания: 400 Вт, потребляемая мощность: 470 Вт", "mismatch"),
    ("Мощность всасывания: 470 Вт / потребляемая мощность: 2100 Вт", "matched"),
    ("Мощность всасывания / потребляемая мощность: 400 Вт / 470 Вт", "unknown"),
    ("Мощность всасывания: 400/470 Вт", "unknown"),
])
def test_power_values_belong_to_their_label_not_a_neighbor(evidence, expected):
    assert _compare_locally("мощность всасывания 470 Вт", evidence)["status"] == expected


@pytest.mark.parametrize("evidence,expected", [
    ("Состав: 100% акрил, 10% шерсть", "mismatch"),
    ("Состав: акрил 100%, шерсть 10%", "mismatch"),
    ("Состав: шерсть 10%, акрил 100%", "mismatch"),
    ("Состав: 10% шерсть и 90% акрил", "mismatch"),
    ("Состав: 100% шерсть", "matched"),
    ("Состав: шерсть 100%", "matched"),
    ("Состав: 100% натуральная шерсть", "matched"),
    ("Состав: шерсть, акрил. Проценты не указаны", "unknown"),
])
def test_percentage_is_bound_to_its_composition_component(evidence, expected):
    assert _compare_locally("100% шерсть", evidence)["status"] == expected


@pytest.mark.parametrize("evidence,expected", [
    ("Нет сертификата ГОСТ 25295-2003", "unknown"),
    ("Сертификат ГОСТ 25295-2003 отсутствует", "unknown"),
    ("Сертификат отсутствует: ГОСТ 25295-2003", "unknown"),
    ("Товар не требует ГОСТ 25295-2003", "unknown"),
    ("Соответствие ГОСТ 25295-2003 не подтверждено", "unknown"),
    ("Не соответствует ГОСТ 25295-2003", "mismatch"),
    ("Соответствует ГОСТ 25295-20030", "unknown"),
    ("Соответствует ГОСТ 25295-2003-2020", "unknown"),
    ("Соответствует ГОСТ 25295-2003", "matched"),
])
def test_standard_identity_and_negation_are_checked_before_substring_match(evidence, expected):
    assert _compare_locally("ГОСТ 25295-2003", evidence)["status"] == expected
