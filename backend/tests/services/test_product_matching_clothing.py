"""Typed garment evidence without dropping any requirement from the PDF."""

import pytest

from app.core.config import settings
from app.services.product_matching import _compare_locally, _requirements, _type_check, evaluate_product_leads
from tests.services.test_product_matching_requirements import JACKET_NAME, JACKET_SPECS


@pytest.fixture(autouse=True)
def no_paid_matching(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_AI_API_KEY", None)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)


@pytest.mark.parametrize("requirement,evidence", [
    ("Материал: шерсть", "Состав: Шерсть 100%"),
    ("Плотная вязка", "Тип вязки: плотная"),
    ("Плотная вязка", "Плотный трикотаж"),
    ("Рукав длинный", "Длина рукава: длинный"),
    ("Рукав длинный", "Длинные рукава и классический воротник"),
    ("Карман — да", "Карманы: прорезные"),
    ("Карман — да", "Два прорезных кармана с клапанами"),
    ("Застежка: молния", "Застёжка на молнии"),
    ("Застежка: молния", "Жакет на замке"),
    ("Горловина разная: круглая, V образная, в воротником", "Вырез горловины: V-образный"),
    ("Горловина разная: круглая, V образная, в воротником", "Воротник: классический"),
    ("Цвет разный, однотонный", "Рисунок: однотонный"),
    ("стиль — пиджачный", "Крой: пиджачный"),
])
def test_equivalent_published_garment_labels_have_verbatim_evidence(requirement, evidence):
    check = _compare_locally(requirement, evidence)

    assert check["status"] == "matched"
    assert check["evidence"] in evidence


@pytest.mark.parametrize("requirement,evidence", [
    ("Материал: шерсть", "Состав: 50% шерсть, 50% акрил"),
    ("Плотная вязка", "Ткань: костюмная шерсть"),
    ("Рукав длинный", "Жакет женский"),
    ("Рукав длинный", "Длинный рукав\nРукав: короткий"),
    ("Карман — да", "Карманы: декоративные, имитация"),
    ("Застежка: молния", "Застежка: молния или пуговицы, вариант по выбору"),
    ("Горловина разная: круглая, V образная, в воротником", "Без классического воротника"),
    ("Цвет разный, однотонный", "Цвет: чёрный"),
    ("стиль — пиджачный", "Классические лацканы и пуговицы"),
    ("Карман — да", "Два кармана, но они не функциональные"),
    ("Рукав длинный", "Длина изделия длинная, рукав не указан"),
    ("Рукав длинный", "Длина изделия длинная, рукав с манжетом"),
    ("женский, повседневный, из трикотажа", "Жакет женский\nМатериал: трикотаж"),
    ("Материал: натуральная мериносовая шерсть", "Состав: Шерсть"),
    ("Жакет женский шерстяной с манжетами", "Жакет женский\nМатериал: Шерсть"),
    ("Рукав длинный с манжетами", "Длина рукава: длинный"),
])
def test_unpublished_ambiguous_or_inferred_garment_values_remain_unknown(requirement, evidence):
    assert _compare_locally(requirement, evidence)["status"] == "unknown"


@pytest.mark.parametrize("requirement,evidence", [
    ("Материал: шерсть", "Материал: не шерсть"),
    ("Материал: шерсть", "Материал: шерсть не используется"),
    ("100% шерсть", "Состав: 100% шерсть не используется"),
    ("Материал: шерсть", "Состав: 100% хлопок"),
    ("Плотная вязка", "Тонкий трикотаж"),
    ("Плотная вязка", "Плотная вязка не предусмотрена"),
    ("Рукав длинный", "Длина рукава: не длинный"),
    ("Рукав длинный", "Длинные рукава не предусмотрены"),
    ("Карман — да", "Два кармана не предусмотрены"),
    ("Карман — да", "Без карманов"),
    ("Застежка: молния", "Классические лацканы и застёжка на пуговицах"),
    ("Застежка: молния", "Не предусмотрена застежка на молнии"),
    ("Цвет разный, однотонный", "Костюмная шерсть со сплошным микроузором"),
    ("Цвет разный, однотонный", "Однотонный рисунок не предусмотрен"),
])
def test_explicit_garment_negation_and_conflicts_never_confirm_requirement(requirement, evidence):
    assert _compare_locally(requirement, evidence)["status"] == "mismatch"


def test_gender_uses_explicit_own_label_beyond_title_neighborhood():
    evidence = "Жакет CDV\nОписание модели\nМатериал: Шерсть\nСостав: Шерсть 100%\nРазмер: 46\nЦвет: синий\nПол: женщины"
    check = _type_check(JACKET_NAME, evidence)

    assert check["status"] == "matched"
    assert "Пол: женщины" in check["evidence"]
    assert _type_check(JACKET_NAME, evidence.replace("Пол: женщины", "Акция для женщин"))["status"] == "unknown"


def test_title_and_explicit_gender_disagreement_requires_review():
    assert _type_check(JACKET_NAME, "Жакет женский\nПол: мужчины")["status"] == "unknown"


def _lead(evidence):
    return {"url": "https://shop.example.kz/p/jacket", "page_verified": True,
            "is_product_page": True, "availability": "InStock", "evidence_text": evidence}


@pytest.mark.asyncio
async def test_corrected_cdv_source_confirms_only_what_it_publishes():
    # The supplied own-page wording has wool, pockets, buttons and a micro-pattern;
    # it does not establish long sleeves, dense knit, a zipper or the ГОСТ.
    evidence = (
        "Жакет CDV\n"
        "Однобортный жакет приталенного кроя из костюмной шерсти со сплошным микроузором.\n"
        "Классические лацканы и застёжка на пуговицах.\n"
        "Два прорезных кармана с клапанами.\n"
        "Материал: Шерсть\nСостав: Шерсть 100%\nВид: Однобортные жакеты\nПол: женщины"
    )
    result = (await evaluate_product_leads(JACKET_NAME, JACKET_SPECS, [_lead(evidence)]))[0]
    checks = {check["requirement"]: check for check in result["checks"]}

    assert len(result["checks"]) == len(_requirements(JACKET_NAME, JACKET_SPECS)) == 11
    assert result["checks"][0]["status"] == "matched"
    assert checks["Жакет женский шерстяной"]["status"] == "matched"
    assert checks["Карман — да"]["status"] == "matched"
    assert checks["Застежка: молния"]["status"] == "mismatch"
    assert checks["Плотная вязка"]["status"] == "unknown"
    assert checks["Рукав длинный"]["status"] == "unknown"
    assert checks["ГОСТ 25295-2003"]["status"] == "unknown"
    assert result["match_status"] == "mismatch"


@pytest.mark.asyncio
async def test_all_eleven_requirements_need_affirmative_own_evidence():
    evidence = (
        "Жакет женский\nМатериал: Шерсть\nТип вязки: плотная\nВоротник: классический\n"
        "Рисунок: однотонный\nДлина рукава: длинный\nКарманы: прорезные\nЗастёжка: молния\n"
        "Крой: пиджачный\nСоответствует ГОСТ 25295-2003"
    )
    result = (await evaluate_product_leads(JACKET_NAME, JACKET_SPECS, [_lead(evidence)]))[0]

    assert len(result["checks"]) == 11
    assert result["match_status"] == "matched"
    assert all(check["status"] == "matched" and check["evidence"] for check in result["checks"])
    missing_standard = (await evaluate_product_leads(JACKET_NAME, JACKET_SPECS, [_lead(evidence.replace("Соответствует ГОСТ 25295-2003", "Сертификат по запросу"))]))[0]
    assert missing_standard["match_status"] == "partial"


@pytest.mark.parametrize("policy", [None, "zipper_only", "unknown", "allow_alternatives_from_page"])
def test_closure_remains_strict_without_explicit_supported_user_policy(policy):
    requirements = _requirements(JACKET_NAME, JACKET_SPECS, closure_policy=policy)

    assert requirements == _requirements(JACKET_NAME, JACKET_SPECS)
    assert any(requirement["text"] == "Застежка: молния" for requirement in requirements)


def test_user_clarification_replaces_only_the_name_derived_closure_check():
    strict = _requirements(JACKET_NAME, JACKET_SPECS)
    clarified = _requirements(JACKET_NAME, JACKET_SPECS, closure_policy="allow_alternatives")

    assert len(clarified) == len(strict) == 11
    assert [row for row in strict if row["id"] != "r1"] == [row for row in clarified if row["id"] != "r1"]
    assert clarified[1]["text"] == "Допустимые застёжки: молния, пуговицы или без застёжки"
    assert any(row["text"] == "ГОСТ 25295-2003" for row in clarified)
    assert any(row["text"] == "Плотная вязка" for row in clarified)


@pytest.mark.asyncio
@pytest.mark.parametrize("closure", ["Застёжка на пуговицах", "Без застёжки"])
async def test_same_product_closure_passes_only_after_explicit_user_clarification(closure):
    evidence = (
        "Жакет женский\nМатериал: Шерсть\nТип вязки: плотная\nВоротник: классический\n"
        f"Рисунок: однотонный\nДлина рукава: длинный\nКарманы: прорезные\n{closure}\n"
        "Крой: пиджачный\nСоответствует ГОСТ 25295-2003"
    )
    strict = (await evaluate_product_leads(JACKET_NAME, JACKET_SPECS, [_lead(evidence)]))[0]
    clarified = (await evaluate_product_leads(JACKET_NAME, JACKET_SPECS, [_lead(evidence)], closure_policy="allow_alternatives"))[0]

    assert strict["match_status"] == "mismatch"
    assert clarified["match_status"] == "matched"
    assert len(strict["checks"]) == len(clarified["checks"]) == 11


@pytest.mark.asyncio
async def test_closure_policy_does_not_confirm_other_unpublished_attributes():
    evidence = "Жакет женский\nЗастёжка на пуговицах\nРазрешены пуговицы и модели без застёжки"
    strict = (await evaluate_product_leads(JACKET_NAME, JACKET_SPECS, [_lead(evidence)]))[0]
    clarified = (await evaluate_product_leads(JACKET_NAME, JACKET_SPECS, [_lead(evidence)], closure_policy="allow_alternatives"))[0]

    assert strict["match_status"] == "mismatch"
    assert clarified["match_status"] == "partial"
    assert next(check for check in clarified["checks"] if check["requirement"] == "ГОСТ 25295-2003")["status"] == "unknown"
    assert next(check for check in clarified["checks"] if check["requirement"] == "Плотная вязка")["status"] == "unknown"
