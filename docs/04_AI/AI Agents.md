# BINOM AI — AI Agents v1.0

**Документ:** AI Agents  
**Версия:** 1.0  
**Дата:** 2026-07-09  
**Статус:** ✅ Утверждён  
**Автор:** AI Engineer  
**Связанные документы:** [AI Architecture.md](../02_Architecture/AI%20Architecture.md), [Prompt Library.md](./Prompt%20Library.md)

---

## 1. Обзор агентной системы

BINOM AI использует мульти-агентную архитектуру с тремя специализированными агентами и одним оркестратором. Каждый агент отвечает за строго определённую задачу и не вмешивается в зону ответственности другого.

```
┌─────────────────────────────────────────────────────────────────┐
│                    Agent Orchestrator                           │
│                (бизнес-логика в services/)                      │
└──────────┬──────────────┬──────────────┬─────────────────────-──┘
           │              │              │
    ┌──────▼──────┐ ┌─────▼──────┐ ┌────▼──────────┐
    │  AGENT 1    │ │  AGENT 2   │ │   AGENT 3     │
    │  Document   │ │  Chat      │ │   Generation  │
    │  Analysis   │ │  Agent     │ │   Agent       │
    └─────────────┘ └────────────┘ └───────────────┘
```

---

## 2. AGENT 1: Document Analysis Agent

### 2.1 Описание

**ID:** `agent_analysis_v1`  
**Файл:** `app/ai/analysis_agent.py`  
**Цель:** Полный структурированный анализ технического задания

### 2.2 Триггеры

| Событие | Действие |
|---------|----------|
| Документ загружен и распарсен | Автоматический запуск |
| Пользователь нажал "Повторить анализ" | Принудительный перезапуск |
| Загружен новый документ (замена) | Сброс и новый запуск |

### 2.3 Входные данные

```python
@dataclass
class AnalysisAgentInput:
    project_id: str
    document_id: str
    document_text: str         # Полный текст ТЗ (после парсинга)
    document_metadata: dict    # Название, дата, страницы
    company_profile: dict      # Профиль компании для контекста
    language: str = "ru"       # Язык документа
```

### 2.4 Выходные данные

```python
@dataclass
class AnalysisAgentOutput:
    # Статус
    status: str                          # "completed" | "partial" | "failed"
    
    # Core результаты
    executive_summary: str
    tender_type: str
    complexity_level: str                # "Low" | "Medium" | "High"
    estimated_duration_days: Optional[int]
    
    # Требования
    technical_requirements: List[Requirement]
    commercial_requirements: List[Requirement]
    legal_requirements: List[Requirement]
    
    # Документы и даты
    required_documents: List[RequiredDocument]
    key_deadlines: List[Deadline]
    
    # Риски и пробелы
    risks: List[Risk]
    missing_info_from_tender: List[str]
    missing_company_data: List[str]
    
    # Технические метаданные
    llm_model: str
    input_tokens: int
    output_tokens: int
    processing_time_ms: int
```

### 2.5 Пошаговая логика агента

```python
class AnalysisAgent:
    
    async def run(self, input: AnalysisAgentInput) -> AnalysisAgentOutput:
        start_time = time.time()
        
        # Шаг 1: Оценка объёма документа
        token_count = self.count_tokens(input.document_text)
        
        # Шаг 2: Решение о стратегии
        if token_count <= 900_000:
            # Single-pass: весь документ в один запрос (Gemini 1.5 Pro)
            result = await self._analyze_single_pass(input)
        else:
            # Multi-pass: chunking + merge (редкий случай)
            result = await self._analyze_with_chunking(input)
        
        # Шаг 3: Валидация результата
        validated = self._validate_output(result)
        
        # Шаг 4: Enrichment (постобработка)
        enriched = self._enrich_output(validated, input)
        
        # Шаг 5: Сохранение в БД
        await self._save_to_db(enriched, input.project_id)
        
        return enriched
    
    async def _analyze_single_pass(
        self, 
        input: AnalysisAgentInput
    ) -> dict:
        """Единый запрос к LLM с полным текстом документа"""
        
        prompt = self.prompt_manager.render(
            "analysis_main",
            document_text=input.document_text,
            company_name=input.company_profile["name"],
            company_specialization=input.company_profile.get("specialization", "")
        )
        
        response = await self.llm_client.generate(
            system_prompt=MASTER_SYSTEM_PROMPT,
            user_prompt=prompt,
            temperature=0.2,
            response_schema=ANALYSIS_OUTPUT_SCHEMA,
            max_tokens=8192
        )
        
        return response
    
    async def _analyze_with_chunking(
        self, 
        input: AnalysisAgentInput
    ) -> dict:
        """Обработка очень больших документов частями"""
        
        chunks = self.chunker.split_by_sections(input.document_text)
        partial_results = []
        
        for chunk in chunks:
            partial = await self._analyze_single_pass(
                AnalysisAgentInput(
                    **{**vars(input), "document_text": chunk}
                )
            )
            partial_results.append(partial)
        
        # Слияние результатов
        return self._merge_analysis_results(partial_results)
    
    def _validate_output(self, raw: dict) -> AnalysisAgentOutput:
        """Pydantic валидация и проверка полноты"""
        try:
            output = AnalysisAgentOutput(**raw)
        except ValidationError as e:
            raise InvalidAgentOutputError(f"Analysis output invalid: {e}")
        
        # Проверка минимальной полноты
        issues = []
        if not output.executive_summary:
            issues.append("Missing executive_summary")
        if not output.technical_requirements and not output.commercial_requirements:
            issues.append("No requirements extracted — likely parsing issue")
        
        if issues:
            logger.warning(f"Analysis quality issues: {issues}")
        
        return output
    
    def _enrich_output(
        self, 
        output: AnalysisAgentOutput,
        input: AnalysisAgentInput
    ) -> AnalysisAgentOutput:
        """Постобработка — добавление вычисленных данных"""
        
        # Автоматическое обнаружение критических сроков
        for deadline in output.key_deadlines:
            if deadline.date:
                days_left = (deadline.date - date.today()).days
                deadline.is_urgent = days_left < 14
        
        # Сортировка рисков по серьёзности
        severity_order = {"High": 0, "Medium": 1, "Low": 2}
        output.risks.sort(key=lambda r: severity_order.get(r.severity, 3))
        
        return output
```

### 2.6 Retry и Error Handling

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=3, max=30),
    retry=retry_if_exception_type((InvalidAgentOutputError, LLMRateLimitError)),
    before_sleep=log_retry_attempt
)
async def _analyze_single_pass(self, input: AnalysisAgentInput) -> dict:
    ...
```

**Fallback:**
- Попытка 1: Gemini 1.5 Pro
- Попытка 2: Gemini 1.5 Pro (повтор)
- Попытка 3: GPT-4o (fallback)
- После 3 попыток: статус `failed`, уведомление пользователя

### 2.7 Стоимость и производительность

| Параметр | Значение |
|---------|----------|
| Среднее время | 20–45 сек |
| P95 время | 90 сек |
| Средние токены (input) | 60,000–180,000 |
| Средние токены (output) | 3,000–8,000 |
| Средняя стоимость | $0.25–$0.80 |

---

## 3. AGENT 2: Clarification Chat Agent

### 3.1 Описание

**ID:** `agent_chat_v1`  
**Файл:** `app/ai/chat_agent.py`  
**Цель:** Диалог с пользователем для сбора данных, необходимых для генерации

### 3.2 Режимы работы

| Режим | Триггер | Описание |
|-------|---------|----------|
| `structured_questioning` | Пользователь открыл чат | AI задаёт подготовленные вопросы последовательно |
| `free_qa` | Пользователь вводит вопрос вне очереди | AI отвечает на произвольный вопрос по ТЗ |
| `clarification` | Ответ пользователя неполный | AI уточняет конкретный аспект |

### 3.3 Входные данные

```python
@dataclass
class ChatAgentInput:
    project_id: str
    session_id: str
    
    # Контекст
    analysis_result: AnalysisAgentOutput
    document_text: str
    company_profile: dict
    
    # История
    conversation_history: List[ChatMessage]
    clarification_context: ClarificationContext
    questions_list: List[Question]          # Подготовленные вопросы
    
    # Текущий запрос
    user_message: str
    mode: str = "structured_questioning"
```

### 3.4 ClarificationContext — схема накопления данных

```python
@dataclass
class ClarificationContext:
    # Данные о компании
    company_experience: Optional[str] = None      # Опыт в аналогичных проектах
    company_certifications: List[str] = field(default_factory=list)
    company_key_projects: List[str] = field(default_factory=list)
    company_employees_count: Optional[int] = None
    
    # Коммерческие условия
    proposed_price: Optional[float] = None
    price_currency: str = "KZT"
    price_type: Optional[str] = None              # "fixed" | "estimate" | "per_unit"
    payment_terms: Optional[str] = None
    warranty_period: Optional[str] = None
    advance_payment: Optional[str] = None
    
    # Техническое решение
    proposed_solution: Optional[str] = None
    technical_approach: Optional[str] = None
    subcontractors: Optional[str] = None
    equipment_suppliers: Optional[str] = None
    
    # Сроки
    proposed_timeline: Optional[str] = None
    mobilization_period: Optional[str] = None
    
    # Произвольные ответы
    custom_answers: Dict[str, str] = field(default_factory=dict)
    
    # Статус
    is_complete: bool = False
    completion_percentage: int = 0
    missing_critical: List[str] = field(default_factory=list)
```

### 3.5 Логика агента

```python
class ChatAgent:
    
    async def process_message(
        self, 
        input: ChatAgentInput
    ) -> ChatAgentOutput:

        # FIX #12: Определяем режим через LLM intent classification
        # (не по наличию символа '?' — тот работает только для английского)
        if len(input.conversation_history) == 0:
            mode = "init"
        else:
            mode = await self._classify_intent(input)

        if mode == "free_qa":
            return await self._handle_free_qa(input)

        elif mode == "structured_questioning" or mode == "init":
            return await self._handle_structured_question(input)

        elif mode == "clarification":
            return await self._handle_clarification(input)
    
    def _detect_mode(self, input: ChatAgentInput) -> str:
        """
        FIX #12: Режим определяется через LLM intent classification,
        а не по наличию символа '?' (эвристика надёжно работает только для английского).

        Примеры проблемы с эвристикой '?':
        - "У нас есть опыт  15 лет?" — это ответ на вопрос, но '?' запускал free_qa
        - "Что требует заказчик" — вопрос без '?' не определялся как вопрос
        """

        # Первое сообщение — всегда init (не требует LLM вызова)
        if len(input.conversation_history) == 0:
            return "init"

        # FIX #12: LLM intent classification для остальных сообщений
        # Быстрый вызов (temperature=0, max_tokens=10) — только одно слово в ответ
        return "__pending_llm_classification__"  # резолвится в process_message

    async def _classify_intent(self, input: ChatAgentInput) -> str:
        """
        FIX #12: Определяет intent сообщения через LLM.
        Быстрый вызов: temperature=0, max_tokens=5 — менее $0.001 за классификацию.
        """
        last_ai_question = self._get_last_ai_question(input.conversation_history)

        classification_prompt = f"""
Ты классифицируешь intent сообщения пользователя в диалоге о тендерной документации.

Последний вопрос AI: {last_ai_question or 'нет'}
Сообщение пользователя: {input.user_message}

Ответь одним словом:
- "answer" — если сообщение является ответом на вопрос AI о компании/цене/опыте
- "question" — если пользователь спрашивает что-то о ТЗ или тендере
Только "answer" или "question".
"""
        result = await self.llm_client.generate(
            system_prompt="",
            user_prompt=classification_prompt,
            temperature=0.0,
            max_tokens=5
        )
        intent = result.get("text", "answer").strip().lower()
        return "free_qa" if intent == "question" else "structured_questioning"
    
    async def _handle_structured_question(
        self, 
        input: ChatAgentInput
    ) -> ChatAgentOutput:
        """Обрабатывает ответ на структурированный вопрос"""
        
        # 1. Извлечь данные из ответа пользователя
        extraction_result = await self._extract_data_from_answer(
            question=self._get_last_ai_question(input.conversation_history),
            answer=input.user_message,
            current_context=input.clarification_context
        )
        
        # 2. Обновить контекст
        updated_context = self._update_context(
            input.clarification_context,
            extraction_result
        )
        
        # 3. Определить следующий вопрос
        next_question = self._get_next_question(
            questions=input.questions_list,
            context=updated_context
        )
        
        # 4. Проверить готовность
        readiness = self._check_readiness(updated_context)
        
        # 5. Сформировать ответ AI
        if readiness.is_complete:
            ai_response = await self._generate_completion_message(updated_context)
        elif next_question:
            ai_response = await self._generate_question_response(
                user_answer=input.user_message,
                next_question=next_question,
                context=updated_context
            )
        else:
            ai_response = await self._generate_summary_message(updated_context)
        
        return ChatAgentOutput(
            user_message_saved=True,
            ai_response=ai_response,
            updated_context=updated_context,
            readiness=readiness,
            next_question_id=next_question.id if next_question else None
        )
    
    async def _handle_free_qa(
        self, 
        input: ChatAgentInput
    ) -> ChatAgentOutput:
        """Отвечает на произвольный вопрос по ТЗ"""
        
        prompt = self.prompt_manager.render(
            "chat_freeqa",
            document_text=input.document_text,
            conversation_history=self._format_history(input.conversation_history),
            user_message=input.user_message
        )
        
        response = await self.llm_client.generate(
            system_prompt=MASTER_SYSTEM_PROMPT,
            user_prompt=prompt,
            temperature=0.5,
            max_tokens=1024,
            stream=True  # Для SSE стриминга
        )
        
        return ChatAgentOutput(
            user_message_saved=True,
            ai_response=response,
            updated_context=input.clarification_context,  # Без изменений
            readiness=self._check_readiness(input.clarification_context),
            is_free_qa=True
        )
    
    def _check_readiness(
        self, 
        context: ClarificationContext
    ) -> ReadinessCheck:
        """Оценивает готовность данных для генерации"""
        
        required_fields = {
            "commercial_proposal": [
                "company_experience",
                "proposed_price",
            ],
            "tech_spec": [
                "proposed_solution",
            ],
            "cover_letter": []  # Только профиль компании
        }
        
        missing = {}
        for doc_type, fields in required_fields.items():
            missing[doc_type] = [
                f for f in fields 
                if not getattr(context, f, None)
            ]
        
        overall_ready = not any(missing.values())
        
        # Вычислить процент
        total_fields = 8  # Ключевые поля
        filled = sum(1 for f in [
            context.company_experience,
            context.proposed_price,
            context.payment_terms,
            context.proposed_solution,
            context.warranty_period,
            context.proposed_timeline,
        ] if f is not None)
        
        percentage = int(filled / total_fields * 100)
        
        return ReadinessCheck(
            is_complete=overall_ready,
            completion_percentage=percentage,
            commercial_proposal_ready=not missing["commercial_proposal"],
            tech_spec_ready=not missing["tech_spec"],
            cover_letter_ready=True,  # Всегда можно (минимум данных)
            missing_critical=missing
        )
```

### 3.6 Производительность

| Параметр | Значение |
|---------|----------|
| Время ответа | 2–8 сек |
| P95 время | 15 сек |
| Средние токены (input) | 5,000–30,000 |
| Средние токены (output) | 200–500 |
| Стоимость per message | $0.01–$0.05 |

---

## 4. AGENT 3: Document Generation Agent

### 4.1 Описание

**ID:** `agent_generation_v1`  
**Файл:** `app/ai/generation_agent.py`  
**Цель:** Генерация финальных тендерных документов

### 4.2 Поддерживаемые типы документов

| doc_type | Название | Секций | Avg. токены output |
|---------|---------|--------|------------------|
| `commercial_proposal` | Коммерческое предложение | 10 | 5,000–8,000 |
| `tech_spec` | Техническая спецификация | 8 | 6,000–10,000 |
| `cover_letter` | Сопроводительное письмо | 5 | 800–1,500 |

### 4.3 Стратегия генерации

```
Section-by-Section Generation (для КП и ТС):

Почему не за один запрос:
1. Качество каждой секции выше при отдельном контексте
2. Можно показывать прогресс пользователю (секция за секцией)
3. Retry отдельных секций без пересоздания всего документа
4. Лучший контроль над длиной и форматом

Схема генерации КП:
┌──────────────────────────────────────────────────┐
│ Pass 1: Генерация sections 1-3                   │
│  → Титул, Введение, О компании                  │
│ Pass 2: Генерация sections 4-6                   │
│  → Понимание проекта, Решение, Соответствие ТЗ  │
│ Pass 3: Генерация sections 7-10                  │
│  → Коммерция, Гарантии, Приложения, Подпись     │
└──────────────────────────────────────────────────┘

Для Cover Letter:
└── Single pass (короткий документ)
```

### 4.4 Логика агента

```python
class GenerationAgent:
    
    SECTION_GROUPS = {
        "commercial_proposal": [
            ["intro", "about_company", "project_understanding"],
            ["tech_solution", "compliance_table", "commercial_terms"],
            ["guarantees", "attachments", "contacts", "signature"]
        ],
        "tech_spec": [
            ["general_info", "scope", "normative_refs"],
            ["technical_description", "specifications", "compliance_table"],
            ["quality_control", "warranty"]
        ],
        "cover_letter": [
            ["header", "greeting", "body", "attachments_list", "closing"]
        ]
    }
    
    async def generate(
        self, 
        input: GenerationAgentInput
    ) -> GenerationAgentOutput:

        # FIX #10: Sequential генерация (instead of parallel asyncio.gather)
        # Каждая секция получает context_so_far — краткое содержание уже
        # сгенерированных секций. Исключает дублирование информации.
        sections = []
        all_section_types = [
            s for group in self.SECTION_GROUPS[input.doc_type] for s in group
        ]
        total = len(all_section_types)

        # FIX #7: Создаём doc_id сразу (partial state виден через generation_status)
        doc_id = await self._create_doc_record(input)

        for idx, section_type in enumerate(all_section_types):

            section = await self._generate_section(
                section_type=section_type,
                input=input,
                context_so_far=sections  # FIX #10: передаём контекст
            )
            sections.append(section)

            # FIX #7: Атомарно сохраняем каждую секцию незамедлительно после генерации.
            # Если следующая секция упадёт — уже сгенерированные секции не потеряются.
            await self._save_section_to_db(section, doc_id)

            # WebSocket: прогресс
            progress = int((idx + 1) / total * 100)
            await self._notify_ws(
                input.project_id,
                event="task:progress",
                data={"progress": progress, "message": f"Генерация раздела {idx + 1}/{total}..."}
            )

        # Сборка финального документа
        document = self._assemble_document(input.doc_type, sections, input)

        # Обновление статуса в БД
        await self._finalize_doc(doc_id, document)

        return GenerationAgentOutput(
            doc_id=doc_id,
            doc_type=input.doc_type,
            sections=sections,
            content_html=document["html"],
            content_json=document["json"],
            status="completed"
        )

    async def resume_generation(
        self,
        doc_id: str,
        input: GenerationAgentInput
    ) -> GenerationAgentOutput:
        """
        FIX #7: Resume генерации с первой неудавшейся секции.
        Используется в `POST /generate/{doc_id}/resume`.
        Уже сохранённые секции не пересоздаются — экономия LLM-вызовов.
        """
        # Загрузить уже сохранённые секции
        saved_sections = await self._load_sections_from_db(doc_id)
        saved_section_types = {s["type"] for s in saved_sections}

        all_section_types = [
            s for group in self.SECTION_GROUPS[input.doc_type] for s in group
        ]
        # Генерировать только отсутствующие секции
        remaining = [s for s in all_section_types if s not in saved_section_types]

        sections = list(saved_sections)  # Стартуем с уже сохранённых
        for section_type in remaining:
            section = await self._generate_section(
                section_type=section_type,
                input=input,
                context_so_far=sections
            )
            sections.append(section)
            await self._save_section_to_db(section, doc_id)

        document = self._assemble_document(input.doc_type, sections, input)
        await self._finalize_doc(doc_id, document)
        return GenerationAgentOutput(doc_id=doc_id, sections=sections, status="completed")
    
    async def _generate_section(
        self,
        section_type: str,
        input: GenerationAgentInput,
        already_generated: List[dict]
    ) -> dict:
        """Генерирует одну секцию документа"""
        
        # Выбор промпта для типа секции
        prompt_name = f"gen_{input.doc_type}_{section_type}"
        
        prompt = self.prompt_manager.render(
            prompt_name,
            **self._prepare_context(input, already_generated)
        )
        
        response = await self.llm_client.generate(
            system_prompt=MASTER_SYSTEM_PROMPT,
            user_prompt=prompt,
            temperature=0.65,
            max_tokens=2048
        )
        
        return {
            "id": f"section_{section_type}",
            "type": section_type,
            "order": self._get_section_order(section_type, input.doc_type),
            "title": self._get_section_title(section_type, input.doc_type),
            "content_html": response["content_html"]
        }
    
    async def regenerate_section(
        self,
        section_id: str,
        instruction: str,
        input: GenerationAgentInput,
        current_sections: List[dict]
    ) -> dict:
        """Перегенерирует только одну секцию"""
        
        current_section = next(s for s in current_sections if s["id"] == section_id)
        other_sections_brief = self._summarize_other_sections(
            current_sections, section_id
        )
        
        prompt = self.prompt_manager.render(
            "gen_section_regen",
            section_title=current_section["title"],
            current_content=current_section["content_html"],
            other_sections_brief=other_sections_brief,
            regeneration_instruction=instruction,
            **self._prepare_context(input, current_sections)
        )
        
        response = await self.llm_client.generate(
            system_prompt=MASTER_SYSTEM_PROMPT,
            user_prompt=prompt,
            temperature=0.7,
            max_tokens=2048
        )
        
        return {**current_section, "content_html": response["content_html"]}
```

### 4.5 Document Assembly

```python
def _assemble_document(
    self, 
    doc_type: str, 
    sections: List[dict],
    input: GenerationAgentInput
) -> dict:
    """Собирает HTML-документ из секций"""
    
    # Титульный лист (без AI — только данные)
    title_page = self._render_title_page(doc_type, input)
    
    # Тело документа
    body_html = "\n\n".join([
        f'<section id="{s["id"]}" class="doc-section" data-type="{s["type"]}">'
        f'<h2>{s["title"]}</h2>'
        f'{s["content_html"]}'
        f'</section>'
        for s in sorted(sections, key=lambda x: x["order"])
    ])
    
    # Полный HTML
    full_html = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <title>{self._get_doc_title(doc_type, input)}</title>
    </head>
    <body class="binom-doc {doc_type}">
        {title_page}
        <div class="doc-body">
            {body_html}
        </div>
    </body>
    </html>
    """
    
    return {
        "html": full_html,
        "json": {
            "doc_type": doc_type,
            "title": self._get_doc_title(doc_type, input),
            "sections": sections,
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "template": f"standard_kz_{doc_type}_v1",
                "company": input.company_profile["name"],
                "word_count": self._count_words(full_html)
            }
        }
    }
```

### 4.6 Производительность

| Документ | Время генерации | Стоимость |
|---------|----------------|-----------|
| КП (полное) | 40–70 сек | $0.35–$0.60 |
| ТС (полная) | 45–80 сек | $0.40–$0.70 |
| Письмо | 15–25 сек | $0.10–$0.20 |

---

## 5. Document Parser (вспомогательный)

**Файл:** `app/ai/document_parser.py`  
**Цель:** Парсинг PDF/DOCX в структурированный текст

```python
class DocumentParser:
    
    async def parse(self, file_path: str, mime_type: str) -> ParsedDocument:
        if mime_type == "application/pdf":
            return await self._parse_pdf(file_path)
        elif mime_type in ["application/docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
            return await self._parse_docx(file_path)
        else:
            raise UnsupportedFileTypeError(f"Cannot parse: {mime_type}")
    
    async def _parse_pdf(self, file_path: str) -> ParsedDocument:
        """PyMuPDF-based PDF parser"""
        
        import fitz  # PyMuPDF
        
        doc = fitz.open(file_path)
        pages = []
        
        for page_num, page in enumerate(doc):
            # Извлечение текста
            text = page.get_text("text")
            
            # Извлечение таблиц (конвертируем в markdown)
            tables = page.find_tables()
            table_md = self._tables_to_markdown(tables)
            
            pages.append(PageContent(
                page_number=page_num + 1,
                text=text,
                tables=table_md
            ))
        
        # Объединяем в один текст с маркерами страниц
        full_text = self._merge_pages(pages)
        
        return ParsedDocument(
            title=self._extract_title(doc),
            total_pages=len(doc),
            full_text=full_text,
            pages=pages,
            token_count=self._count_tokens(full_text),
            language=self._detect_language(full_text[:1000])
        )
    
    async def _parse_docx(self, file_path: str) -> ParsedDocument:
        """python-docx based DOCX parser"""
        
        from docx import Document
        
        doc = Document(file_path)
        sections_text = []
        
        for element in doc.element.body:
            if element.tag.endswith('p'):  # Параграф
                para = element
                style = para.style.name if hasattr(para, 'style') else "Normal"
                text = para.text.strip()
                
                if not text:
                    continue
                
                # Маркируем заголовки
                if style.startswith("Heading"):
                    level = style.split()[-1] if style.split()[-1].isdigit() else "1"
                    sections_text.append(f"\n{'#' * int(level)} {text}\n")
                else:
                    sections_text.append(text)
            
            elif element.tag.endswith('tbl'):  # Таблица
                table_md = self._docx_table_to_markdown(element, doc)
                sections_text.append(f"\n{table_md}\n")
        
        full_text = "\n".join(sections_text)
        
        return ParsedDocument(
            title=doc.core_properties.title or "",
            total_pages=self._estimate_pages(full_text),
            full_text=full_text,
            token_count=self._count_tokens(full_text),
            language=self._detect_language(full_text[:1000])
        )
```

---

## 6. LLM Client (общий для всех агентов)

**Файл:** `app/ai/llm_client.py`

```python
class LLMClient:
    """
    Единый клиент для LLM с автоматическим fallback
    Primary: Gemini 1.5 Pro
    Fallback: GPT-4o (только если estimated_input_tokens < GPT4O_MAX_TOKENS)
    """

    GPT4O_MAX_TOKENS = 120_000  # FIX #4: GPT-4o context = 128k; буфер 8k

    def __init__(self):
        self.gemini = genai.GenerativeModel("gemini-1.5-pro")
        self.openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.current_model = "gemini-1.5-pro"

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 8192,
        response_schema: Optional[dict] = None,
        stream: bool = False,
        estimated_input_tokens: int = 0  # FIX #4: предварительная оценка для fallback guard
    ) -> dict | AsyncGenerator:

        try:
            return await self._call_gemini(
                system_prompt, user_prompt,
                temperature, max_tokens, response_schema, stream
            )

        except (GeminiAPIError, APITimeoutError) as e:
            logger.warning(f"Gemini failed ({e})")
            self.current_model = "gpt-4o"

            # FIX #4: Проверяем размер перед обращением к GPT-4o
            if estimated_input_tokens > self.GPT4O_MAX_TOKENS:
                logger.error(
                    f"Skipping GPT-4o fallback: document too large "
                    f"({estimated_input_tokens} > {self.GPT4O_MAX_TOKENS} tokens). "
                    f"Gemini-only request."
                )
                raise GeminiRequiredError(
                    "Документ слишком большой для резервного AI. "
                    "Повторите попытку позже."
                )

            logger.warning(f"Switching to GPT-4o fallback ({estimated_input_tokens} tokens)")
            return await self._call_openai(
                system_prompt, user_prompt,
                temperature, max_tokens, stream
            )

    async def _call_gemini(self, system_prompt, user_prompt, temperature, max_tokens, schema, stream):
        """Вызов Gemini 1.5 Pro"""

        # FIX #4: использовать реальный tokenizer для подсчёта (count_tokens API Gemini)
        config = genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        if schema:
            config.response_mime_type = "application/json"
            config.response_schema = schema

        if stream:
            return self.gemini.generate_content_async(
                [system_prompt, user_prompt],
                generation_config=config,
                stream=True
            )

        response = await self.gemini.generate_content_async(
            [system_prompt, user_prompt],
            generation_config=config
        )

        return json.loads(response.text) if schema else {"text": response.text}

    async def _call_openai(self, system_prompt, user_prompt, temperature, max_tokens, stream):
        """Вызов GPT-4o как fallback"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = await self.openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            stream=stream
        )

        if stream:
            return response  # AsyncGenerator

        return json.loads(response.choices[0].message.content)


class GeminiRequiredError(Exception):
    """FIX #4: Поднимается когда документ слишком большой для GPT-4o fallback."""
    pass
```

---

## 7. Агентный Оркестратор

**Файл:** `app/services/analysis_service.py`  
**Файл:** `app/services/chat_service.py`  
**Файл:** `app/services/generation_service.py`

Бизнес-логика координации агентов:

```python
class AnalysisService:
    
    async def start_analysis(self, project_id: str, document_id: str) -> str:
        """Запускает задачу анализа через Celery"""
        
        # Получить данные
        document = await self.doc_repo.get(document_id)
        project = await self.proj_repo.get(project_id)
        company = await self.user_repo.get_company(project.company_id)
        
        # Создать запись анализа
        analysis_id = await self.analysis_repo.create(project_id=project_id)
        
        # Поставить в очередь Celery
        task = analyze_document_task.delay(
            analysis_id=analysis_id,
            document_text=document.extracted_text,
            company_profile=company.dict()
        )
        
        return task.id
```

---

## 8. Мониторинг агентов

### Метрики для каждого агента

```python
# Логируем каждый вызов агента
await ai_usage_log_repo.create(
    company_id=company_id,
    user_id=user_id,
    project_id=project_id,
    operation=f"agent_{agent_name}",
    llm_model=llm_client.current_model,
    input_tokens=response.usage.input_tokens,
    output_tokens=response.usage.output_tokens,
    duration_ms=elapsed_ms,
    success=True,
    cost_usd_cents=self._calculate_cost(response.usage)
)
```

### Dashboard метрики (для CTO)

| Метрика | Мониторинг |
|---------|-----------|
| Agent success rate | > 95% |
| Avg analysis time | < 30 сек |
| Avg generation time | < 60 сек |
| JSON parse failures | < 2% |
| LLM fallback rate | < 5% |
| Cost per project | < $2.00 |

---

*Документ подготовлен командой BINOM AI. AI Agents v1.0 — утверждён.*  
*Следующий документ: [Knowledge Base.md](./Knowledge%20Base.md)*
