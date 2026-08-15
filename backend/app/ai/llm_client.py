import os
import json
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from typing import Type, TypeVar, Any
from pydantic import BaseModel
from app.core.config import settings

logger = structlog.get_logger(__name__)

T = TypeVar('T', bound=BaseModel)

# Gemini/OpenAI clients are created per-call: Celery workers run each task in its
# own event loop (asyncio.run), and a module-level client would bind its HTTP
# transport to a loop that gets closed after the first task, breaking later calls
# with "Event loop is closed".
#
# The SDKs are also imported lazily per-call: importing google.generativeai at
# module level adds ~200MB of RSS to every process (uvicorn + celery), which
# triggers OOM kills on the 512MB free instance.

GPT4O_MAX_TOKENS = 120_000

try:
    from google.api_core.exceptions import ResourceExhausted as GoogleRateLimit
except ImportError:
    GoogleRateLimit = type("GoogleRateLimit", (Exception,), {})

try:
    from openai import RateLimitError as OpenAIRateLimit
except ImportError:
    OpenAIRateLimit = type("OpenAIRateLimit", (Exception,), {})


def _should_retry(exc: Exception) -> bool:
    """Do not retry quota/rate-limit errors — they only add load and never recover in time."""
    if isinstance(exc, (GoogleRateLimit, OpenAIRateLimit)):
        logger.warning("llm_rate_limited", error=str(exc)[:300])
        return False
    return True


class AIServiceUnavailableError(Exception):
    pass

class AIQuotaExhaustedError(AIServiceUnavailableError):
    """Raised when the primary (and fallback) AI quota is exhausted for the day."""

class GeminiRequiredError(AIServiceUnavailableError):
    pass

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(_should_retry),
    reraise=True
)
async def _call_gemini(prompt: str, system_prompt: str, schema_class: Type[T]) -> dict:
    """Calls Gemini and expects a JSON output matching the schema."""
    import google.generativeai as genai

    genai.configure(api_key=settings.GOOGLE_AI_API_KEY)

    # We use GenerationConfig to enforce JSON output. 
    # Since we can't always pass pydantic schema directly in older genai versions without issues,
    # we enforce JSON application/json and rely on system prompt for schema structure.
    
    # Generate schema description to append to prompt
    schema_desc = json.dumps(schema_class.model_json_schema(), indent=2)
    full_prompt = f"{system_prompt}\n\nOUTPUT SCHEMA (Respond EXACTLY with this JSON structure):\n{schema_desc}\n\n{prompt}"
    
    gemini_model = genai.GenerativeModel(settings.PRIMARY_LLM_MODEL)
    response = await gemini_model.generate_content_async(
        full_prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
        ),
        request_options={"timeout": 240},
    )
    
    if not response.text:
        raise ValueError("Empty response from Gemini")
        
    return json.loads(response.text)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(_should_retry),
    reraise=True
)
async def _call_openai(prompt: str, system_prompt: str, schema_class: Type[T]) -> dict:
    """Calls GPT-4o using Structured Outputs."""
    from openai import AsyncOpenAI

    openai_client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        timeout=240,
        max_retries=2,
    )
    try:
        response = await openai_client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            response_format=schema_class,
            temperature=0.0
        )
    finally:
        await openai_client.close()
    
    if not response.choices:
        raise ValueError("Empty response from OpenAI")
        
    # parse() returns the pydantic object in .parsed
    return response.choices[0].message.parsed.model_dump()


async def call_llm(prompt: str, system_prompt: str, schema_class: Type[T], estimated_tokens: int = 0) -> tuple[T, str]:
    """
    Orchestrates the LLM call with a fallback strategy.
    Returns a tuple of (Parsed Model, model_name).
    """
    try:
        logger.info("llm_call_started", model=settings.PRIMARY_LLM_MODEL, estimated_tokens=estimated_tokens)
        result_dict = await _call_gemini(prompt, system_prompt, schema_class)
        # Validate through Pydantic
        parsed_result = schema_class.model_validate(result_dict)
        return parsed_result, settings.PRIMARY_LLM_MODEL

    except (GoogleRateLimit, OpenAIRateLimit) as e:
        logger.error("llm_quota_exhausted", error=str(e)[:300])
        raise AIQuotaExhaustedError(
            "Достигнут дневной лимит AI-запросов. Попробуйте позже или обратитесь к администратору."
        )

    except Exception as e:
        logger.warning("gemini_call_failed", error=str(e))
        
        if estimated_tokens > GPT4O_MAX_TOKENS:
            logger.error(
                "document_too_large_for_fallback", 
                estimated_tokens=estimated_tokens, 
                limit=GPT4O_MAX_TOKENS
            )
            raise GeminiRequiredError(
                "Document is too large for the fallback AI. Please try again later."
            )
            
        logger.info("falling_back_to_openai", model="gpt-4o")
        try:
            result_dict = await _call_openai(prompt, system_prompt, schema_class)
            parsed_result = schema_class.model_validate(result_dict)
            return parsed_result, "gpt-4o"
        except (GoogleRateLimit, OpenAIRateLimit) as fallback_quota:
            logger.error("openai_fallback_quota_exhausted", error=str(fallback_quota)[:300])
            raise AIQuotaExhaustedError(
                "Достигнут дневной лимит AI-запросов. Попробуйте позже или обратитесь к администратору."
            )
        except Exception as fallback_e:
            logger.error("openai_fallback_failed", error=str(fallback_e))
            raise AIServiceUnavailableError("Both Primary and Fallback AI services failed.")
