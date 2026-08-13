import json
import structlog
from typing import Dict, Any, List, Optional

from app.ai.llm_client import call_llm, AIServiceUnavailableError
from app.schemas.chat import ChatReplyOutput
from app.core.supabase import supabase_admin
from app.core.config import settings

FIELD_ORDER = ["experience", "price", "deadline_plan", "licenses"]

_KEYWORDS = {
    "experience": ["опыт", "проект", "объект", "реализован", "выполнил", "выполненн", "аналог"],
    "price": ["цена", "тенге", "стоимост", "сумм", "млн", "млрд", "бюджет", "предложени"],
    "deadline_plan": ["срок", "дней", "недел", "месяц", "дня", "быстр", "успе", "дней"],
    "licenses": ["лиценз", "сертифик", "допуск", "аттестац", "разрешени"],
}


def classify_fields(text: str) -> Dict[str, str]:
    """Determine ALL clarification fields the user message addresses.

    A single message can contain several answers (e.g. price + deadline +
    experience); return every matched field so no data is lost.
    """
    lowered = text.lower()
    result: Dict[str, str] = {}
    for field in FIELD_ORDER:
        if any(k in lowered for k in _KEYWORDS[field]):
            result[field] = text.strip()
    return result


def classify_field(text: str):
    """First matched clarification field (kept for compatibility)."""
    matched = list(classify_fields(text))
    return matched[0] if matched else None

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = """Вы — AI-копайлот BINOM AI для подготовки заявок на государственные закупки/тендеры.

Вы ведёте уточняющий диалог с пользователем и собираете структурированные данные для коммерческого предложения (КП). Поля для сбора:
- experience: опыт компании в аналогичных работах (количество и примеры проектов);
- price: ориентировочная цена предложения (в тенге);
- deadline_plan: сроки выполнения работ относительно дедлайна тендера;
- licenses: наличие необходимых лицензий/допусков/сертификатов.

ПРАВИЛА (строго):
1. Поле message_field всегда возвращайте null — классификацию выполняет система.
2. Задавайте в text следующий недостающий вопрос из Current clarification data (по порядку experience → price → deadline_plan → licenses), по ОДНОМУ вопросу.
3. На вопросы про содержание тендера отвечайте по контексту (Extracted text of the tender).
4. is_complete=true ТОЛЬКО когда все 4 поля уже заполнены ИЛИ пользователь явно просит завершить.
5. Отвечайте кратко и по-русски."""


def _truncate(text: str, limit: int = 60000) -> str:
    return text if len(text) <= limit else text[:limit]


async def _load_document_texts(company_id: str, project_id: str, doc_paths: List[str]) -> str:
    """Try to load extracted texts from Supabase Storage; return joined snippet."""
    chunks: List[str] = []
    bucket = "extracted-texts"
    for path in doc_paths:
        try:
            async with supabase_admin.get_client() as client:
                response = await client.get(f"/storage/v1/object/{bucket}/{path}")
                if response.status_code == 200:
                    chunks.append(_truncate(response.text, 20000))
        except Exception as e:
            logger.debug("chat_text_load_failed", path=path, error=str(e))
    return "\n\n---\n\n".join(chunks)


class ChatAgent:
    @staticmethod
    async def build_context_prompt(db, project, company_id: str) -> str:
        """Assemble tender context (document texts) for the LLM prompt."""
        from sqlalchemy import select
        from app.db.models.document import Document

        result = await db.execute(
            select(Document).where(
                Document.project_id == project.id,
                Document.is_current == True,  # noqa: E712
            )
        )
        docs = result.scalars().all()

        doc_meta = "\n".join(
            f"- {d.filename} (status: {d.processing_status}, title: {d.doc_title or '—'})"
            for d in docs
        )
        if not docs:
            return "Documents: no documents uploaded for this project yet."

        extracted = ""
        if settings.SUPABASE_URL:
            extracted = await _load_document_texts(
                company_id,
                str(project.id),
                [d.extracted_text_path for d in docs if d.extracted_text_path],
            )

        parts = [f"Tenders documents:\n{doc_meta}"]
        if extracted:
            parts.append(
                f"Extracted text of the tender (use it to answer questions about the tender):\n{extracted}"
            )
        return "\n\n".join(parts)

    @staticmethod
    def _history_from_messages(messages: List[Any]) -> str:
        return "\n".join(
            f"{'Пользователь' if m.role == 'user' else 'Копайлот'}: {m.content}"
            for m in messages[-12:]
        )

    @staticmethod
    def _merge_context(
        old: Dict[str, Any], update: Dict[str, Any], answered_field: Optional[str]
    ) -> Dict[str, Any]:
        merged = {k: v for k, v in old.items() if not k.startswith("_")}
        merged.update(update)
        if answered_field:
            merged["_last_question"] = answered_field
        else:
            merged.pop("_last_question", None)
        return merged

    @staticmethod
    async def answer(
        db,
        project,
        company_id: str,
        user_content: str,
        session,
        messages: List[Any],
    ) -> ChatReplyOutput:
        """Produce the assistant reply (LLM with a graceful fallback)."""
        context_prompt = await ChatAgent.build_context_prompt(db, project, company_id)
        history = ChatAgent._history_from_messages(messages)
        current_context = json.dumps(session.context, ensure_ascii=False)

        prompt = (
            f"Tender context:\n{context_prompt}\n\n"
            f"Current clarification data:\n{current_context}\n\n"
            f"Dialogue history:\n{history}\n\n"
            f"User's message: {user_content}"
        )

        logger.info(
            "chat_prompt_ctx",
            context=current_context[:400],
            history_tail=history[-300:],
        )

        try:
            parsed, model = await call_llm(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
                schema_class=ChatReplyOutput,
                estimated_tokens=len(prompt) // 4,
            )
            # Server-side guard: field classification is deterministic (LLM is
            # unreliable at mapping free-form answers to fields).
            fields = classify_fields(user_content)
            merged = ChatAgent._merge_context(session.context, fields, None)
            missing = [f for f in FIELD_ORDER if not merged.get(f)]
            if parsed.is_complete and missing:
                parsed.is_complete = False
                parsed.text = _HEURISTIC_QUESTIONS[missing[0]]
            parsed.message_field = next(iter(fields), None)
            logger.info(
                "chat_llm_reply",
                model=model,
                is_complete=parsed.is_complete,
                message_field=parsed.message_field,
                missing=missing,
            )
            return parsed
        except AIServiceUnavailableError:
            logger.warning("chat_llm_unavailable_falling_back_to_heuristics")
            return ChatAgent._heuristic_reply(session, user_content, {})
        except Exception as exc:
            logger.warning("chat_llm_error", error=str(exc), exc_info=True)
            return ChatAgent._heuristic_reply(session, user_content, {})

    @staticmethod
    def _heuristic_reply(session, user_content: str, db_context: Dict[str, Any]) -> ChatReplyOutput:
        """Deterministic fallback: sequential clarification state machine."""
        db_context = {**db_context, **(session.context or {})}
        fields = classify_fields(user_content) if user_content.strip() else {}
        current = {**db_context, **fields}
        missing = [f for f in FIELD_ORDER if not current.get(f)]
        if not missing:
            return ChatReplyOutput(
                text="Спасибо! Вся информация собрана — можно переходить к генерации коммерческого предложения.",
                message_field=None,
                is_complete=True,
            )
        next_q = missing[0]
        return ChatReplyOutput(
            text=_HEURISTIC_QUESTIONS[next_q],
            message_field=next(iter(fields), None),
            is_complete=False,
        )


_HEURISTIC_QUESTIONS = {
    "experience": "Какой опыт в аналогичных работах у вашей компании? Укажите количество реализованных проектов.",
    "price": "Какую ориентировочную цену предложения вы планируете (в тенге)?",
    "deadline_plan": "Какой срок выполнения работ вы готовы предложить относительно дедлайна тендера?",
    "licenses": "Есть ли у компании необходимые лицензии, допуски или сертификаты по данному виду работ?",
}