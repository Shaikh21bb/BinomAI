import re
import structlog
from typing import Optional
from app.ai.llm_client import call_llm
from app.ai.prompt_manager import get_analysis_prompt, TENDER_ANALYSIS_SYSTEM_PROMPT
from app.schemas.analysis import TenderAnalysisOutput, Requirement, Risk, KeyDeadline, MissingInfo
from app.core.supabase import supabase_admin
from app.core.config import settings

logger = structlog.get_logger(__name__)


class AnalysisAgent:
    @staticmethod
    def heuristic_analysis(text_content: str) -> tuple[TenderAnalysisOutput, dict]:
        """
        Deterministic fallback analysis when the LLM is unavailable (quota, network).
        Produces a basic but structured analysis from the extracted text via regex heuristics.
        """
        import time
        start_time = time.time()
        sample = text_content[:20000]

        # --- Tender type by keywords ---
        type_keywords = {
            "construction": ["строит", "ремонт", "монтаж", "подряд", "смп", "объект", "бетон"],
            "supply": ["поставк", "товар", "оборудован", "закупк"],
            "services": ["услуг", "обслуживан", "сервис"],
        }
        lowered = sample.lower()
        tender_type = "Прочие (mixed/unspecified)"
        for kind, keywords in type_keywords.items():
            if any(kw in lowered for kw in keywords):
                tender_type = {"construction": "Строительство", "supply": "Поставка", "services": "Услуги"}[kind]
                break

        # --- Duration from "срок ... N дней/месяцев" ---
        duration = 0
        m = re.search(r'срок[^.]{0,80}?(\d{1,4})\s*(дн|календарн)', lowered, re.IGNORECASE)
        if m:
            duration = int(m.group(1))
        else:
            m = re.search(r'срок[^.]{0,80}?(\d{1,2})\s*мес', lowered, re.IGNORECASE)
            if m:
                duration = int(m.group(1)) * 30

        # --- Deadlines (dates) ---
        deadlines = []
        for m in list(re.finditer(r'\b(\d{2})[.\-](\d{2})[.\-](\d{4})\b', sample))[:5]:
            deadlines.append(
                KeyDeadline(
                    event=f"Дата из документа (дд.мм.гггг)",
                    date=f"{m.group(1)}.{m.group(2)}.{m.group(3)}",
                    is_hard_deadline=False,
                )
            )

        # --- Commercial: sums in tenge ---
        commercial = []
        for m in list(re.finditer(r'(\d[\d\s]{2,12})\s*(тенге|₸|тг\.?)', sample, re.IGNORECASE))[:5]:
            commercial.append(
                Requirement(
                    id=f"req_c{len(commercial) + 1:03d}",
                    text=f"Финансовое условие: {m.group(1).strip()} {m.group(2)}",
                    category="financial",
                    is_mandatory=False,
                    source_section="—",
                )
            )
        if not commercial:
            commercial.append(
                Requirement(
                    id="req_c001",
                    text="Сумма/цена не обнаружены в тексте — уточнить у заказчика",
                    category="financial",
                    is_mandatory=False,
                )
            )

        # --- Legal: licenses / certificates ---
        legal = []
        legal_kw = ["лицензи", "сертификат", "соответстви", "свидетельств", "разрешен"]
        for kw in legal_kw:
            for m in list(re.finditer(rf'[^.]{{0,120}}{kw}[^.]{{0,120}}\.', sample, re.IGNORECASE))[:2]:
                legal.append(
                    Requirement(
                        id=f"req_l{len(legal) + 1:03d}",
                        text=m.group(0).strip(),
                        category="legal",
                        is_mandatory=True,
                        source_section="—",
                    )
                )

        # --- Summary: first meaningful sentences ---
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', sample) if len(s.strip()) > 20]
        summary = " ".join(sentences[:3])[:600] or (sample[:300] + "…")
        summary = f"[Базовый анализ (LLM недоступен)] {summary}"

        complexity = "low" if len(text_content) < 5000 else ("medium" if len(text_content) < 20000 else "high")

        missing = [
            MissingInfo(
                description="Полноценный AI-анализ недоступен (исчерпан дневной лимит запросов)",
                impact="Требования выделены автоматически по ключевым словам",
                clarification_question="Повторить глубокий анализ позже?",
            )
        ]

        output = TenderAnalysisOutput(
            executive_summary=summary,
            tender_type=tender_type,
            complexity_level=complexity,
            estimated_duration_days=duration,
            commercial_requirements=commercial,
            legal_requirements=legal,
            key_deadlines=deadlines,
            risks=[
                Risk(
                    id="risk_001",
                    description="Анализ выполнен автоматически, возможны пропуски требований",
                    severity="Medium",
                    risk_type="qualification",
                )
            ],
            missing_info_from_tender=missing,
            missing_company_data=["Полные данные компании (специализация, опыт)"],
        )

        metadata = {
            "llm_model": "heuristic-fallback",
            "input_tokens": len(text_content) // 4,
            "output_tokens": 0,
            "processing_time_ms": int((time.time() - start_time) * 1000),
        }
        return output, metadata

    @staticmethod
    async def run_analysis(
        document_id: str, 
        project_id: str, 
        company_id: str,
        company_context: str = ""
    ) -> tuple[TenderAnalysisOutput, dict]:
        """
        Orchestrates the AI Analysis:
        1. Loads the extracted text from Supabase Storage.
        2. Estimates tokens.
        3. Prepares prompts and calls LLM (with fallback logic).
        4. Returns the validated Pydantic object and metadata.
        """
        import time
        start_time = time.time()
        
        # 1. Load Extracted Text from Storage
        bucket = "extracted-texts"
        text_path = f"{company_id}/{project_id}/{document_id}.txt"
        
        try:
            async with supabase_admin.get_client() as client:
                response = await client.get(f"/storage/v1/object/{bucket}/{text_path}")
                if response.status_code != 200:
                    raise ValueError(f"Could not load extracted text from storage: {response.status_code}")
                text_content = response.text
        except Exception as e:
            logger.error("failed_to_load_text_for_analysis", error=str(e), path=text_path)
            raise
            
        # 2. Prepare Prompt & Estimate tokens
        # Very rough estimation: 4 chars per token. tiktoken could be used for exact OpenAI count,
        # but 4 chars/token is a safe generic assumption for English/Russian.
        estimated_input_tokens = len(text_content) // 4
        
        prompt = get_analysis_prompt(text_content, company_context)
        
        # 3. Call LLM
        parsed_result, model_used = await call_llm(
            prompt=prompt,
            system_prompt=TENDER_ANALYSIS_SYSTEM_PROMPT,
            schema_class=TenderAnalysisOutput,
            estimated_tokens=estimated_input_tokens
        )
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # We don't have exact output token counts from the wrapper easily without 
        # intercepting raw responses, so we estimate them based on JSON length
        estimated_output_tokens = len(parsed_result.model_dump_json()) // 4
        
        metadata = {
            "llm_model": model_used,
            "input_tokens": estimated_input_tokens,
            "output_tokens": estimated_output_tokens,
            "processing_time_ms": processing_time_ms,
        }
        
        return parsed_result, metadata
