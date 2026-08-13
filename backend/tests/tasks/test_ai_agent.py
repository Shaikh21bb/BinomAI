import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.schemas.analysis import TenderAnalysisOutput
from app.ai.llm_client import call_llm, GeminiRequiredError, AIServiceUnavailableError
from app.core.config import settings

@pytest.fixture
def mock_gemini():
    with patch("app.ai.llm_client._call_gemini") as mock:
        yield mock

@pytest.fixture
def mock_openai():
    with patch("app.ai.llm_client._call_openai") as mock:
        yield mock

# Sample valid output dictionary
SAMPLE_RESULT = {
    "executive_summary": "Test",
    "tender_type": "Construction",
    "complexity_level": "medium",
    "estimated_duration_days": 100,
    "technical_requirements": [],
    "commercial_requirements": [],
    "legal_requirements": [],
    "required_documents": [],
    "key_deadlines": [],
    "risks": [],
    "missing_info_from_tender": [],
    "missing_company_data": []
}

@pytest.mark.asyncio
async def test_call_llm_primary_success(mock_gemini, mock_openai):
    mock_gemini.return_value = SAMPLE_RESULT
    
    result, model = await call_llm(
        prompt="test",
        system_prompt="system",
        schema_class=TenderAnalysisOutput,
        estimated_tokens=500
    )
    
    assert model == settings.PRIMARY_LLM_MODEL
    assert result.executive_summary == "Test"
    mock_openai.assert_not_called()

@pytest.mark.asyncio
async def test_call_llm_fallback_success(mock_gemini, mock_openai):
    mock_gemini.side_effect = Exception("API Down")
    mock_openai.return_value = SAMPLE_RESULT
    
    result, model = await call_llm(
        prompt="test",
        system_prompt="system",
        schema_class=TenderAnalysisOutput,
        estimated_tokens=500
    )
    
    assert model == "gpt-4o"
    assert result.executive_summary == "Test"
    mock_openai.assert_called_once()

@pytest.mark.asyncio
async def test_call_llm_no_fallback_large_token(mock_gemini, mock_openai):
    mock_gemini.side_effect = Exception("API Down")
    
    with pytest.raises(GeminiRequiredError):
        await call_llm(
            prompt="test",
            system_prompt="system",
            schema_class=TenderAnalysisOutput,
            estimated_tokens=200_000 # > 120,000
        )
        
    mock_openai.assert_not_called()

@pytest.mark.asyncio
async def test_call_llm_both_fail(mock_gemini, mock_openai):
    mock_gemini.side_effect = Exception("API Down")
    mock_openai.side_effect = Exception("API Down Too")
    
    with pytest.raises(AIServiceUnavailableError):
        await call_llm(
            prompt="test",
            system_prompt="system",
            schema_class=TenderAnalysisOutput,
            estimated_tokens=500
        )


def test_heuristic_analysis_basic():
    from app.ai.analysis_agent import AnalysisAgent

    text = (
        "Техническое задание на строительство объекта.\n"
        "Срок выполнения работ: 120 дней.\n"
        "Цена договора: 25 000 000 тенге.\n"
        "Требуется лицензия на строительно-монтажные работы.\n"
        "Срок подачи заявки: до 15.09.2026."
    )
    output, meta = AnalysisAgent.heuristic_analysis(text)

    assert output.estimated_duration_days == 120
    assert output.commercial_requirements, "expected a commercial requirement"
    assert any("25 000 000" in r.text for r in output.commercial_requirements)
    assert output.legal_requirements, "expected a legal requirement"
    assert output.key_deadlines, "expected a deadline"
    assert meta["llm_model"] == "heuristic-fallback"
    assert "строительств" in output.executive_summary.lower() or "Строительств" in output.tender_type
