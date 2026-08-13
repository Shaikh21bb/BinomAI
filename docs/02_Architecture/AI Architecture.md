# BINOM AI — AI Architecture v1.0

**Документ:** AI Architecture  
**Версия:** 1.0  
**Дата:** 2026-07-09  
**Статус:** ✅ Утверждён  
**Автор:** AI Engineer / CTO  
**Связанные документы:** [System Architecture.md](./System%20Architecture.md), [Prompt Library.md](../04_AI/Prompt%20Library.md), [AI Agents.md](../04_AI/AI%20Agents.md)

---

## 1. Обзор AI-архитектуры

BINOM AI использует мульти-агентную архитектуру на основе LLM, оркестрируемую через LangChain. Каждый AI-агент специализирован на конкретной задаче и работает в рамках чётко определённого контекста.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          BINOM AI — AI Architecture                         │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                       AI Orchestration Layer                         │   │
│  │                     (LangChain + Custom Logic)                       │   │
│  │                                                                      │   │
│  │  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │   │
│  │  │  Document        │  │  Clarification   │  │  Generation      │   │   │
│  │  │  Analysis Agent  │  │  Chat Agent      │  │  Agent           │   │   │
│  │  │                  │  │                  │  │                  │   │   │
│  │  │  • Requirements  │  │  • Q&A Dialog    │  │  • КП Generator  │   │   │
│  │  │  • Risk Radar    │  │  • Context Mgmt  │  │  • ТС Generator  │   │   │
│  │  │  • Gap Analysis  │  │  • Free Q&A      │  │  • Letter Gen    │   │   │
│  │  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘   │   │
│  │           │                     │                      │             │   │
│  └───────────┼─────────────────────┼──────────────────────┼─────────────┘   │
│              │                     │                      │                 │
│  ┌───────────▼─────────────────────▼──────────────────────▼─────────────┐   │
│  │                         LLM Client Layer                             │   │
│  │                                                                      │   │
│  │   Primary: Google Gemini 1.5 Pro          Fallback: OpenAI GPT-4o   │   │
│  │   Context: 1,000,000 tokens               Context: 128,000 tokens    │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                      Supporting Infrastructure                       │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────┐  │   │
│  │  │  Document    │  │  Prompt      │  │  Context     │  │  RAG    │  │   │
│  │  │  Parser      │  │  Manager     │  │  Manager     │  │  Layer  │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └─────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Выбор LLM моделей

### 2.1 Primary LLM: Google Gemini 1.5 Pro

| Характеристика | Значение |
|---------------|----------|
| Context Window | 1,000,000 токенов (~750,000 слов) |
| Input cost | $3.50 / 1M tokens |
| Output cost | $10.50 / 1M tokens |
| Avg. response time | 5–15 сек (зависит от размера) |
| Max output | 8,192 токенов |
| Multimodal | Да (текст + изображения) |
| Языки | Русский — отличное качество |

**Почему Gemini 1.5 Pro:**
- 1M контекст = весь большой ТЗ (300+ стр.) за один запрос
- Не нужен chunking для анализа (минус сложность)
- Лучшая цена за качество в категории
- Будущее: мультимодальность для анализа чертежей

### 2.2 Fallback LLM: OpenAI GPT-4o

| Характеристика | Значение |
|---------------|----------|
| Context Window | 128,000 токенов |
| Input cost | $5.00 / 1M tokens |
| Output cost | $15.00 / 1M tokens |
| Avg. response time | 3–10 сек |
| Языки | Русский — отличное качество |

**Когда используется GPT-4o:**
- Gemini API недоступен (503, timeout)
- Gemini возвращает некорректный JSON
- Специфические задачи, где GPT-4o лучше
- **estimated_input_tokens ≤ 120,000** (FIX #4: при большем документе — fallback невозможен)

### 2.3 Fallback Strategy

```python
GPT4O_MAX_TOKENS = 120_000  # FIX #4: GPT-4o context = 128k; буфер 8k для safety

async def call_llm(prompt: str, schema: dict, estimated_input_tokens: int = 0) -> dict:
    """
    LLM с автоматическим fallback.
    estimated_input_tokens: предварительная оценка токенов запроса.
    При превышении контекста GPT-4o — fallback невозможен, используется chunking.
    """
    try:
        # Primary: Gemini 1.5 Pro
        response = await gemini_client.generate(
            prompt=prompt,
            response_schema=schema,
            timeout=60
        )
        return parse_and_validate(response, schema)

    except (GeminiAPIError, TimeoutError) as e:
        logger.warning(f"Gemini failed: {e}")

        # FIX #4: Проверяем, помещается ли запрос в контекст GPT-4o (128k токенов)
        if estimated_input_tokens > GPT4O_MAX_TOKENS:
            logger.error(
                f"Document too large for GPT-4o fallback "
                f"({estimated_input_tokens} tokens > {GPT4O_MAX_TOKENS} limit). "
                f"Gemini-only document — cannot fallback."
            )
            # Не пытаемся вызвать GPT-4o — это даст context_length_exceeded
            # Вместо этого: явная ошибка с понятным сообщением пользователю
            raise GeminiRequiredError(
                "Документ слишком большой для резервного AI. "
                "Повторите попытку позже или загрузите документ меньшего объёма."
            )

        logger.warning(f"Switching to GPT-4o fallback (tokens: {estimated_input_tokens})")
        try:
            # Fallback: GPT-4o (только для документов < 120k токенов)
            response = await openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                timeout=60
            )
            return parse_and_validate(response, schema)

        except OpenAIError as e:
            logger.error(f"Both LLMs failed: {e}")
            raise AIServiceUnavailableError("AI service temporarily unavailable")
```

**Исключения:**

```python
class GeminiRequiredError(AIServiceUnavailableError):
    """Поднимается когда документ слишком большой для GPT-4o fallback."""
    pass
```

**HTTP ответ при GeminiRequiredError:**
```json
{
  "success": false,
  "error": {
    "code": "AI_FALLBACK_UNAVAILABLE",
    "message": "Документ слишком большой для резервного AI. Повторите попытку позже."
  }
}
```

---

## 3. Document Parser

### 3.1 PDF Parsing

```
PDF File
   │
   ▼
[PyMuPDF (fitz)]
   │
   ├── Extract text by page
   ├── Extract tables (as markdown)
   ├── Extract metadata (title, author, date)
   └── Detect language (langdetect)
   │
   ▼
[Text Cleaner]
   │
   ├── Remove headers/footers (если дубли)
   ├── Fix encoding issues
   ├── Normalize whitespace
   └── Preserve structure (headings, lists)
   │
   ▼
[Document Chunker]
   │
   ├── If total tokens < 900,000: send as single chunk (Gemini)
   └── If total tokens > 900,000: split into chapters/sections
   │
   ▼
[Structured Document Object]
   {
     "title": "...",
     "total_pages": 45,
     "sections": [...],
     "full_text": "...",
     "token_count": 52000
   }
```

### 3.2 DOCX Parsing

```
DOCX File
   │
   ▼
[python-docx]
   │
   ├── Extract paragraphs (with styles: Heading 1, 2, Normal)
   ├── Extract tables (as markdown)
   ├── Extract metadata
   └── Preserve list structure
   │
   ▼
[Same pipeline as PDF from Text Cleaner step]
```

### 3.3 Chunking Strategy (для больших документов)

Применяется только если документ > 900,000 токенов (~675,000 слов, ~2,250 страниц). На практике, большинство ТЗ < 300 страниц = не нужен chunking для Gemini 1.5 Pro.

```python
def chunk_document(text: str, max_tokens: int = 100_000) -> List[str]:
    """
    Разбивает документ на чанки по разделам (не разрезая предложения)
    """
    sections = split_by_headings(text)  # По заголовкам разделов
    chunks = []
    current_chunk = ""

    for section in sections:
        # FIX #17: использовать реальный tokenizer, не heuristic len/4
        # len(text) / 4 даёт ошибку до 30% для кириллицы (UTF-8 = 2 байта/символ)
        if count_tokens(current_chunk + section) < max_tokens:
            current_chunk += section
        else:
            chunks.append(current_chunk)
            current_chunk = section

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def count_tokens(text: str) -> int:
    """
    FIX #17: Реальный подсчёт токенов через Gemini count_tokens API.
    Не используем heuristic len(text)/4 — ошибка до 30% для русского текста.
    Используем API с кэшированием — бесплатно и быстро.
    """
    model = genai.GenerativeModel("gemini-1.5-pro")
    result = model.count_tokens(text)
    return result.total_tokens
```

---

## 4. AI Agents (детальное описание)

### 4.1 Document Analysis Agent

**Задача:** Анализ загруженного ТЗ и извлечение структурированных данных.

**Trigger:** Загрузка и парсинг документа завершён.

**Input:**
```python
class AnalysisInput(BaseModel):
    document_text: str          # Полный текст ТЗ
    company_profile: dict       # Профиль компании (для контекста)
    project_name: str           # Название проекта
```

**Output (Structured JSON):**
```python
class AnalysisOutput(BaseModel):
    # 1. Краткое резюме
    executive_summary: str                    # 2-5 предложений
    
    # 2. Требования
    technical_requirements: List[Requirement]  # Технические требования
    commercial_requirements: List[Requirement] # Коммерческие требования
    legal_requirements: List[Requirement]      # Юридические требования
    
    # 3. Обязательные документы
    required_documents: List[RequiredDocument]
    
    # 4. Риски
    risks: List[Risk]
    
    # 5. Gap Analysis
    missing_info_from_tender: List[str]        # Что не указано в ТЗ
    missing_company_data: List[str]            # Что нужно от компании
    
    # 6. Метаданные
    tender_type: str                           # "EPC" | "supply" | "services" | "construction"
    complexity_level: str                      # "Low" | "Medium" | "High"
    estimated_duration_days: Optional[int]
    key_deadlines: List[Deadline]

class Requirement(BaseModel):
    id: str
    text: str                      # Текст требования
    category: str                  # Категория
    is_mandatory: bool             # Обязательное или желательное
    source_section: str            # Раздел ТЗ, откуда взято
    source_page: Optional[int]

class Risk(BaseModel):
    id: str
    description: str
    severity: str                  # "High" | "Medium" | "Low"
    risk_type: str                 # "legal" | "technical" | "commercial" | "deadline"
    mitigation: str                # Рекомендованное действие
    source_section: str
```

**Pipeline агента:**

```
Document Text
     │
     ▼
[System Prompt: TZ Analysis Expert]
     │
     ├── Task 1: Extract requirements (structured)
     ├── Task 2: Identify risks
     ├── Task 3: Gap analysis
     ├── Task 4: Classify tender
     └── Task 5: Summarize
     │
     ▼
[Gemini 1.5 Pro]
(single call, full document in context)
     │
     ▼
[Pydantic Validation]
     │
     ▼
[Save to DB: analysis table]
     │
     ▼
[WebSocket notify: analysis_complete]
```

**Температура:** 0.2 (детерминированность важнее креативности)  
**Estimated tokens:** Input 50k–200k, Output 3k–8k  
**Estimated cost per analysis:** $0.10–$0.80  
**Estimated time:** 15–45 сек

---

### 4.2 Clarification Chat Agent

**Задача:** Задавать уточняющие вопросы пользователю и собирать необходимую информацию для генерации документов.

**Trigger:** Анализ ТЗ завершён, пользователь открыл чат.

**Input:**
```python
class ChatInput(BaseModel):
    analysis_result: AnalysisOutput       # Результат анализа ТЗ
    company_profile: dict                 # Профиль компании
    conversation_history: List[Message]   # История диалога
    user_message: Optional[str]           # Текущее сообщение пользователя
    mode: str                             # "questioning" | "free_qa"
```

**Chat Modes:**

**Mode 1: Structured Questioning (автоматические вопросы)**
```
AI logic:
1. На основе gap_analysis формирует список вопросов
2. Задаёт вопросы по одному (или группами по теме)
3. Сохраняет ответы в structured context
4. Когда все критические вопросы отвечены → сигнализирует "Ready to generate"
```

**Mode 2: Free Q&A (произвольные вопросы)**
```
Пользователь спрашивает → AI ищет ответ в тексте ТЗ → отвечает с цитатой
```

**Clarification Context (накапливается):**
```python
class ClarificationContext(BaseModel):
    # Данные о компании
    company_experience: Optional[str]
    company_certifications: List[str]
    company_key_projects: List[str]
    
    # Коммерческие данные
    proposed_price: Optional[float]
    price_currency: str
    payment_terms: Optional[str]
    warranty_period: Optional[str]
    
    # Технические данные
    proposed_solution: Optional[str]
    technical_approach: Optional[str]
    subcontractors: Optional[str]
    
    # Дополнительно
    custom_answers: Dict[str, str]   # Вопрос → Ответ
    is_complete: bool                # Достаточно для генерации?
```

**Estimated tokens per message:** Input 5k–30k, Output 200–500  
**Estimated cost per conversation:** $0.05–$0.30  
**Response time:** 2–8 сек

---

### 4.3 Document Generation Agent

**Задача:** Генерация профессиональных тендерных документов на основе анализа и уточненного контекста.

**Trigger:** Пользователь нажимает «Сгенерировать [тип документа]».

**Input:**
```python
class GenerationInput(BaseModel):
    document_type: str                      # "commercial_proposal" | "tech_spec" | "cover_letter"
    analysis_result: AnalysisOutput         # Результат анализа ТЗ
    clarification_context: ClarificationContext  # Собранные ответы
    company_profile: dict                   # Профиль компании
    document_text: str                      # Исходный текст ТЗ (для контекста)
    template_name: str                      # Шаблон документа
```

**Стратегия генерации по типу документа:**

**⚠️ FIX #10 — Sequential генерация секций (не параллельная):**

Секции генерируются **последовательно** — каждая следующая получает `context_so_far` (краткое содержание предыдущих секций). Это исключает дублирование контента между секциями одной группы.

Параллельная генерация была невозможна корректно: секции одной группы не знали о содержании друг друга → одна информация (например, «15 лет опыта») могла появиться в нескольких секциях.

```python
# Вместо asyncio.gather() — sequential с накоплением контекста
for section_type in all_sections_ordered:
    section = await self._generate_section(
        section_type=section_type,
        input=input,
        context_so_far=sections  # Все уже сгенерированные секции
    )
    sections.append(section)
    # FIX #7: сохраняем каждую секцию сразу после генерации
    await self._save_section_to_db(section, doc_id)
    await self._notify_progress(input.project_id, sections, all_sections)
```

#### Коммерческое предложение (КП)

```
Sections to generate (последовательно):
1. Титульный лист → format only (no AI)
2. Вводная часть → AI (1-2 абзаца)
3. О компании → Template + company_profile data
4. Понимание проекта → AI (на основе резюме ТЗ + context_so_far секций 1-3)
5. Предлагаемое решение → AI (на основе tech analysis + clarification + context_so_far)
6. Технические характеристики → AI (requirements table + context_so_far)
7. Коммерческие условия → Template + clarification data (цена, сроки)
8. Гарантии и условия → Template + clarification data
9. Приложения → Checklist (required_documents)
10. Контактная информация → company_profile data
```

#### Техническая спецификация (ТС)

```
Sections to generate:
1. Общие сведения → AI (на основе резюме ТЗ)
2. Область применения → AI
3. Нормативные ссылки → Template (ГОСТ/СНиП) + AI additional
4. Техническое описание → AI (детально)
5. Технические характеристики → AI (таблица параметров)
6. Соответствие требованиям ТЗ → AI (таблица: Требование | Наше решение | Статус)
7. Методы испытаний → Template + AI
8. Упаковка и транспортировка → Template
9. Гарантийные обязательства → Template + clarification
```

#### Сопроводительное письмо

```
Sections to generate:
1. Шапка → Template + company_profile
2. Адресат → Template (from ТЗ metadata)
3. Вступление → AI (1 абзац)
4. Основная часть → AI (2-3 абзаца)
5. Перечень документов → AI (based on required_documents)
6. Заключение → Template
7. Подпись → company_profile
```

**Параметры генерации:**

| Параметр | Значение |
|---------|----------|
| Temperature | 0.65 (баланс качества и разнообразия) |
| Max output tokens | 4,096 (КП), 6,144 (ТС), 1,024 (Письмо) |
| Estimated cost per doc | $0.15–$0.50 |
| Estimated time | 20–60 сек |

---

## 5. Context Management

### 5.1 Project Context Window

Для каждого проекта формируется **единый контекстный объект**:

```python
class ProjectContext(BaseModel):
    """Полный контекст проекта для AI-агентов"""
    
    # Метаданные проекта
    project_id: str
    project_name: str
    created_at: datetime
    
    # Данные компании
    company: CompanyProfile
    
    # Документ
    document_filename: str
    document_text: str              # Полный текст ТЗ
    document_metadata: dict
    
    # Результат анализа
    analysis: Optional[AnalysisOutput]
    
    # История диалога
    conversation: List[Message]
    clarification: ClarificationContext
    
    # Сгенерированные документы
    generated_docs: List[GeneratedDocument]
```

### 5.2 Token Budget Management

```python
class TokenBudget:
    """Управление токенами в контексте"""
    
    GEMINI_MAX = 900_000  # 10% buffer от 1M
    
    @staticmethod
    def estimate_context_tokens(context: ProjectContext) -> int:
        tokens = 0
        tokens += count_tokens(context.document_text)
        tokens += count_tokens(str(context.analysis))
        tokens += count_tokens(str(context.conversation[-10:]))  # Last 10 messages
        tokens += count_tokens(str(context.company))
        return tokens
    
    @staticmethod
    def trim_if_needed(context: ProjectContext) -> ProjectContext:
        if TokenBudget.estimate_context_tokens(context) > TokenBudget.GEMINI_MAX:
            # Trim conversation history (keep last 5 messages)
            context.conversation = context.conversation[-5:]
            # If still too large, summarize older conversation
        return context
```

---

## 6. RAG (Retrieval-Augmented Generation)

RAG используется для обогащения генерации документов нормативной базой.

### 6.1 Knowledge Base для RAG

```
Knowledge Base:
├── regulations/
│   ├── GOST/              # ГОСТ строительные нормы (RU)
│   ├── SNIP/              # СНиП
│   ├── SP/                # Своды правил
│   └── KZ_laws/           # Законы РК о закупках
│
├── templates/
│   ├── commercial_proposal/  # Примеры хорошего КП
│   ├── tech_spec/            # Примеры ТС
│   └── cover_letter/         # Примеры писем
│
└── glossary/
    └── construction_terms.json  # Строительные термины
```

### 6.2 RAG Pipeline

```python
class RAGLayer:
    """
    RAG для нормативной базы РК
    """
    
    async def retrieve_relevant_norms(
        self, 
        requirements: List[str],
        tender_type: str
    ) -> List[NormDocument]:
        """
        Поиск релевантных норм и стандартов для данного тендера
        """
        # 1. Embed requirements query
        query_embedding = await embed(requirements)
        
        # 2. Vector search in knowledge base
        results = await self.vector_store.similarity_search(
            embedding=query_embedding,
            k=5,
            filter={"tender_type": tender_type}
        )
        
        # 3. Return relevant norms with citations
        return [NormDocument(
            norm_id=r.metadata["id"],
            title=r.metadata["title"],
            relevant_section=r.page_content,
            citation=r.metadata["citation"]
        ) for r in results]
```

**В MVP**: RAG — опциональная функция. Нормативная база добавляется в System Prompt статически для наиболее распространённых типов тендеров.

**В Phase 2**: Полный вектор-поиск через pgvector (Supabase).

---

## 7. Prompt Architecture

Детальные промпты описаны в [Prompt Library.md](../04_AI/Prompt%20Library.md).

### 7.0 Prompt Version Tracking — FIX #11

Каждый AI-вызов использует конкретную версию промпта. Версия сохраняется в БД вместе с результатом.

**Зачем это критично:**
- Retry анализа должен использовать ту же версию промпта, что и оригинальный анализ (иначе структура output может измениться)
- При апгрейде промпта старые проекты (in-flight) продолжают работать на старой версии
- A/B тестирование промптов без влияния на production

```python
# В analysis_results и generated_documents сохраняется prompt_version
# analysis_results.prompt_version = "v1"  # уже добавлено в DB Schema
# generated_documents.prompt_version = "v1"  # добавить в схему

class PromptVersion:
    """Версии промптов — изменяются только при breaking change в output schema."""
    ANALYSIS_V1 = "analysis_v1"       # Текущая production версия
    CHAT_V1 = "chat_v1"
    GENERATION_KP_V1 = "gen_kp_v1"
    GENERATION_TS_V1 = "gen_ts_v1"
    GENERATION_LETTER_V1 = "gen_letter_v1"

# При retry анализа — использовать prompt_version из original record:
existing = await analysis_repo.get_current(project_id)
retry_prompt_version = existing.prompt_version  # Не брать latest, брать original
```

**Правило смены версии:** новая версия промпта создаётся только если меняется output JSON schema. Косметические изменения текста промпта — не требуют смены версии.

### 7.1 Prompt Hierarchy

```
┌─────────────────────────────────────────────────┐
│ Level 1: MASTER SYSTEM PROMPT                   │
│ (общий для всей системы)                        │
│                                                 │
│ "Ты — AI Copilot для тендерной подготовки       │
│  в Казахстане. Ты эксперт в строительстве..."   │
└────────────────────┬────────────────────────────┘
                     │
     ┌───────────────┼───────────────┐
     │               │               │
┌────▼──────┐  ┌─────▼─────┐  ┌─────▼─────┐
│ Analysis  │  │  Chat     │  │Generation │
│ Prompt    │  │  Prompt   │  │ Prompts   │
│           │  │           │  │           │
│ Level 2   │  │ Level 2   │  │ Level 2   │
└────┬──────┘  └─────┬─────┘  └─────┬─────┘
     │               │               │
┌────▼──────┐  ┌─────▼─────┐  ┌─────▼─────────────┐
│ Requirements│ │ Questions │  │ КП | ТС | Letter  │
│ Risks      │ │ Free QA   │  │ Prompt per type   │
│ Gaps       │ │           │  │                   │
│ Level 3   │  │ Level 3   │  │ Level 3           │
└───────────┘  └───────────┘  └───────────────────┘
```

### 7.2 Prompt Template System

```python
class PromptManager:
    """
    Управление промптами с переменными
    """
    
    templates: Dict[str, PromptTemplate] = {}
    
    def render(self, template_name: str, **kwargs) -> str:
        template = self.templates[template_name]
        return template.format(**kwargs)
    
    def get_analysis_prompt(self, doc_text: str, company: dict) -> str:
        return self.render(
            "analysis_main",
            document_text=doc_text,
            company_name=company["name"],
            company_specialization=company.get("specialization", "строительство")
        )
```

---

## 8. AI Quality Assurance

### 8.1 Output Validation

Каждый AI-ответ проходит валидацию через Pydantic:

```python
class AIResponseValidator:
    
    @staticmethod
    def validate_analysis(raw_response: str) -> AnalysisOutput:
        """
        Парсит и валидирует JSON-ответ агента анализа
        """
        try:
            data = json.loads(raw_response)
            return AnalysisOutput(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            # Retry with fix prompt
            raise InvalidAIResponseError(f"AI returned invalid structure: {e}")
    
    @staticmethod
    def check_completeness(analysis: AnalysisOutput) -> List[str]:
        """
        Проверяет полноту анализа
        """
        issues = []
        if not analysis.executive_summary:
            issues.append("Missing executive_summary")
        if not analysis.technical_requirements:
            issues.append("No technical requirements extracted")
        if not analysis.risks:
            issues.append("No risks identified (suspicious for any real tender)")
        return issues
```

### 8.2 Retry Logic

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(InvalidAIResponseError)
)
async def call_analysis_agent(input: AnalysisInput) -> AnalysisOutput:
    response = await llm_client.generate(prompt)
    return AIResponseValidator.validate_analysis(response)
```

### 8.3 Hallucination Prevention

**Ключевые правила в промптах:**

```
1. "Используй ТОЛЬКО информацию из предоставленного документа"
2. "НЕ придумывай требования, которых нет в тексте"
3. "Если информация отсутствует — явно укажи 'Не указано в ТЗ'"
4. "Цитируй раздел ТЗ для каждого требования"
5. "Не используй общие фразы без конкретики из документа"
```

### 8.4 Quality Metrics

| Метрика | Целевое значение | Как измеряется |
|---------|-----------------|---------------|
| JSON Parse Success Rate | > 98% | Автоматически в коде |
| Requirements Recall | > 85% | Ручная проверка на 20 ТЗ |
| Risk Precision | > 80% | Экспертная оценка |
| Generation Relevance | > 80% | CSAT оценка пользователей |
| Hallucination Rate | < 5% | Ручная проверка |

---

## 9. AI Cost Estimation

### 9.1 Стоимость на одного пользователя (один тендер)

| Операция | Input Tokens | Output Tokens | Стоимость |
|---------|-------------|--------------|-----------|
| Document Analysis (Gemini) | ~80,000 | ~5,000 | ~$0.33 |
| Chat Q&A (5-10 messages) | ~20,000 | ~3,000 | ~$0.10 |
| КП Generation | ~100,000 | ~4,000 | ~$0.39 |
| ТС Generation | ~100,000 | ~6,000 | ~$0.41 |
| Cover Letter | ~80,000 | ~1,000 | ~$0.29 |
| **Итого на тендер** | | | **~$1.50** |

*При курсе 450 тг/$ = ~675 тг на тендер*

### 9.2 Unit Economics

| Тариф | Цена/мес | Тендеров/мес | AI Cost | Gross Margin |
|-------|----------|-------------|---------|-------------|
| Starter | 25,000 тг | 5 | ~3,375 тг | ~86% |
| Professional | 75,000 тг | 20 | ~13,500 тг | ~82% |
| Enterprise | 200,000 тг | Unlimited | ~50,000 тг | ~75% |

### 9.3 Оптимизация стоимости

| Оптимизация | Экономия |
|------------|---------|
| Кэширование результатов анализа | 100% для повторных запросов |
| Параметр `temperature=0.2` снижает retries | ~20% |
| Structured output (меньше объяснений) | ~15% |
| Trim conversation history | ~10% |
| Cacheable system prompts (Gemini feature) | ~20% на input |

---

## 10. AI Safety и этика

### 10.1 Данные пользователей

```
❌ Данные тендеров НЕ используются для дообучения AI
❌ Содержание ТЗ НЕ логируется в открытых системах
❌ Конкурентные данные (цены) НЕ хранятся дольше сессии
✅ Все данные изолированы по компании (RLS)
✅ Пользователь может удалить свои данные
✅ Данные хранятся в зашифрованном виде
```

### 10.2 AI Limitations Disclosure

В интерфейсе всегда отображается disclaimer:

> *«BINOM AI — инструмент автоматизации. Все сгенерированные документы требуют проверки специалистом перед подачей. AI может допускать ошибки.»*

---

## 11. Future AI Capabilities (Roadmap)

| Функция | Фаза | Описание |
|---------|------|----------|
| Fine-tuned model | Phase 3 | Дообучение на казахстанских тендерах |
| Multimodal analysis | Phase 3 | Анализ чертежей и схем из ТЗ |
| Automatic pricing | Phase 4 | AI-оценка стоимости проекта |
| Win prediction | Phase 4 | Оценка шансов на победу в тендере |
| Contract analysis | Phase 4 | Contract Copilot модуль |
| Voice input | Phase 5 | Голосовой ввод данных |

---

*Документ подготовлен командой BINOM AI. AI Architecture v1.0 — утверждён.*  
*Следующий документ: [Database Schema.md](./Database%20Schema.md)*
