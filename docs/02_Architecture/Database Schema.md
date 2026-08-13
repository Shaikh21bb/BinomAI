# BINOM AI — Database Schema v1.0

**Документ:** Database Schema  
**Версия:** 1.0  
**Дата:** 2026-07-09  
**Статус:** ✅ Утверждён  
**Автор:** CTO / Solution Architect  
**Связанные документы:** [System Architecture.md](./System%20Architecture.md), [API Specification.md](./API%20Specification.md)

---

## 1. Обзор схемы

**База данных:** PostgreSQL 15 (через Supabase)  
**Управление:** Row Level Security (RLS) для изоляции данных компаний  
**Нотация:** SQL + описание бизнес-логики

### ER-диаграмма (высокий уровень)

```
                    ┌──────────────┐
                    │   companies  │
                    │  (tenant)    │
                    └──────┬───────┘
                           │ 1:N
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼──┐  ┌──────▼──┐  ┌─────▼────┐
       │  users  │  │ projects │  │templates │
       └──────┬──┘  └──────┬───┘  └──────────┘
              │            │
              │     ┌──────┼──────────────────┐
              │     │      │                  │
              │  ┌──▼──┐ ┌─▼──────────┐ ┌────▼──────────┐
              │  │ docs │ │  analysis  │ │  generated_   │
              │  │      │ │  results   │ │  documents    │
              │  └──────┘ └────────────┘ └───────────────┘
              │                                │
              └──────────┐                     │
                    ┌────▼─────┐               │
                    │   chat   │          ┌────▼──────┐
                    │ messages │          │  exports  │
                    └──────────┘          └───────────┘
```

---

## 2. Таблицы

### 2.1 companies (Тенант — Компания)

```sql
CREATE TABLE companies (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Основная информация
    name            VARCHAR(255)    NOT NULL,
    bin_iin         VARCHAR(12)     UNIQUE,         -- БИН/ИИН компании
    legal_address   TEXT,
    actual_address  TEXT,
    
    -- Контакты
    phone           VARCHAR(20),
    email           VARCHAR(255),
    website         VARCHAR(255),
    
    -- Брендинг
    logo_url        TEXT,                           -- URL логотипа в Storage
    
    -- Профиль компании (для AI-контекста)
    specialization  TEXT,                           -- "строительство", "EPC", etc.
    description     TEXT,                           -- Краткое описание компании
    founded_year    INTEGER,
    employee_count  INTEGER,
    
    -- Реквизиты для документов
    director_name   VARCHAR(255),                   -- ФИО директора
    director_title  VARCHAR(255),                   -- Должность (для подписи)
    bank_name       VARCHAR(255),
    bank_account    VARCHAR(50),
    bank_bik        VARCHAR(20),
    
    -- Подписка
    plan            VARCHAR(50)     NOT NULL DEFAULT 'trial',  -- 'trial' | 'starter' | 'professional' | 'enterprise'
    plan_expires_at TIMESTAMPTZ,
    
    -- Метаданные
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    is_active       BOOLEAN         NOT NULL DEFAULT true
);

-- Индексы
CREATE INDEX idx_companies_bin_iin ON companies(bin_iin);

-- RLS
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;

CREATE POLICY "companies_own_access" ON companies
    FOR ALL
    USING (id = (auth.jwt() ->> 'company_id')::UUID);

-- Trigger для updated_at
CREATE TRIGGER set_companies_updated_at
    BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
```

**Поля:** 28 | **Индексов:** 1 + PK | **RLS:** Да

---

### 2.2 users (Пользователи)

```sql
-- Supabase автоматически создаёт таблицу auth.users
-- Мы создаём публичную таблицу с расширенными данными

CREATE TABLE public.users (
    id              UUID            PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    company_id      UUID            NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    
    -- Профиль
    full_name       VARCHAR(255),
    job_title       VARCHAR(255),                   -- Должность
    phone           VARCHAR(20),
    avatar_url      TEXT,
    
    -- Роль в системе
    role            VARCHAR(50)     NOT NULL DEFAULT 'user',  -- 'owner' | 'admin' | 'user' | 'viewer'
    
    -- Настройки
    language        VARCHAR(10)     NOT NULL DEFAULT 'ru',    -- 'ru' | 'kz'
    timezone        VARCHAR(50)     NOT NULL DEFAULT 'Asia/Almaty',
    email_notifications BOOLEAN     NOT NULL DEFAULT true,
    
    -- Онбординг
    onboarding_completed BOOLEAN    NOT NULL DEFAULT false,
    
    -- Метаданные
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    is_active       BOOLEAN         NOT NULL DEFAULT true
);

-- Индексы
CREATE INDEX idx_users_company_id ON users(company_id);
CREATE INDEX idx_users_role ON users(company_id, role);

-- RLS
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_own_company" ON public.users
    FOR ALL
    USING (company_id = (auth.jwt() ->> 'company_id')::UUID);

CREATE POLICY "users_own_profile" ON public.users
    FOR ALL
    USING (id = auth.uid());
```

**Поля:** 18 | **Роли:** owner > admin > user > viewer

---

### 2.3 projects (Тендерные проекты)

```sql
CREATE TABLE projects (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      UUID            NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    created_by      UUID            NOT NULL REFERENCES public.users(id),
    
    -- Основная информация
    name            VARCHAR(500)    NOT NULL,        -- Название тендера
    customer_name   VARCHAR(500),                   -- Заказчик
    customer_bin    VARCHAR(12),                    -- БИН заказчика
    
    -- Статус
    status          VARCHAR(50)     NOT NULL DEFAULT 'draft',
    -- 'draft' | 'analyzing' | 'clarifying' | 'generating' | 'review' | 'done' | 'submitted' | 'archived'
    
    -- Дедлайн
    deadline_at     TIMESTAMPTZ,
    submission_at   TIMESTAMPTZ,                    -- Дата фактической подачи
    
    -- Метаданные тендера (заполняется из ТЗ)
    tender_type     VARCHAR(100),                   -- 'EPC' | 'construction' | 'supply' | 'services'
    tender_number   VARCHAR(255),                   -- Номер тендера (из goszakup)
    complexity      VARCHAR(20),                    -- 'low' | 'medium' | 'high'
    
    -- Теги
    tags            TEXT[],                         -- Массив тегов
    
    -- Заметки пользователя
    notes           TEXT,
    
    -- Метаданные
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- Индексы
CREATE INDEX idx_projects_company_id ON projects(company_id);
CREATE INDEX idx_projects_status ON projects(company_id, status);
CREATE INDEX idx_projects_created_at ON projects(company_id, created_at DESC);

-- RLS
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;

CREATE POLICY "projects_company_access" ON projects
    FOR ALL
    USING (company_id = (auth.jwt() ->> 'company_id')::UUID);
```

**Статусы проекта:**

```
draft → analyzing → clarifying → generating → review → done → submitted
                                                              ↘ archived
```

---

### 2.4 documents (Загруженные ТЗ)

```sql
CREATE TABLE documents (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID            NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    company_id      UUID            NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    uploaded_by     UUID            NOT NULL REFERENCES public.users(id),
    
    -- Файл
    filename        VARCHAR(500)    NOT NULL,        -- Оригинальное имя файла
    file_size_bytes BIGINT          NOT NULL,
    mime_type       VARCHAR(100)    NOT NULL,        -- 'application/pdf' | 'application/docx'
    storage_path    TEXT            NOT NULL,        -- Путь в Supabase Storage
    
    -- Извлечённый контент
    -- FIX #6: extracted_text убран из PostgreSQL (TOAST bloat при 500+ документах).
    -- Полный текст хранится как .txt файл в Storage bucket 'extracted-texts'.
    -- В БД хранится только путь к файлу.
    extracted_text_path TEXT,                       -- Путь в Storage: {company_id}/{project_id}/{doc_id}.txt
    page_count      INTEGER,
    token_count     INTEGER,                        -- Количество LLM-токенов
    language        VARCHAR(10),                    -- 'ru' | 'kz' | 'en'
    
    -- Статус обработки
    processing_status VARCHAR(50)   NOT NULL DEFAULT 'uploading',
    -- 'uploading' | 'processing' | 'ready' | 'error'
    
    error_message   TEXT,                           -- Если processing_status = 'error'
    
    -- Метаданные извлечённые из документа
    doc_title       VARCHAR(500),                   -- Заголовок из ТЗ
    doc_number      VARCHAR(255),                   -- Номер документа
    doc_date        DATE,                           -- Дата документа
    
    -- Версионность
    version         INTEGER         NOT NULL DEFAULT 1,
    is_current      BOOLEAN         NOT NULL DEFAULT true,  -- Активная версия
    
    -- Метаданные
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- Индексы
CREATE INDEX idx_documents_project_id ON documents(project_id);
CREATE INDEX idx_documents_company_id ON documents(company_id);
CREATE INDEX idx_documents_current ON documents(project_id, is_current) WHERE is_current = true;

-- RLS
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY "documents_company_access" ON documents
    FOR ALL
    USING (company_id = (auth.jwt() ->> 'company_id')::UUID);
```

---

### 2.5 analysis_results (Результаты AI-анализа)

```sql
-- FIX #3: Убран UNIQUE на project_id.
-- Причина: UNIQUE делал физически невозможным retry анализа (INSERT нарушал constraint).
-- Решение: версионирование через is_current (аналогично таблице documents).
CREATE TABLE analysis_results (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID            NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    document_id     UUID            NOT NULL REFERENCES documents(id),
    company_id      UUID            NOT NULL REFERENCES companies(id) ON DELETE CASCADE,

    -- Версионирование (аналогично documents.is_current)
    is_current      BOOLEAN         NOT NULL DEFAULT true,  -- Только одна запись = true на project_id
    prompt_version  VARCHAR(20)     NOT NULL DEFAULT 'v1',  -- Версия промпта, которым сделан анализ

    -- Статус анализа
    status          VARCHAR(50)     NOT NULL DEFAULT 'pending',
    -- 'pending' | 'processing' | 'completed' | 'failed'
    
    -- Резюме
    executive_summary TEXT,
    
    -- Метаданные тендера
    tender_type     VARCHAR(100),
    complexity_level VARCHAR(20),
    estimated_duration_days INTEGER,
    
    -- Требования (JSONB)
    technical_requirements  JSONB   DEFAULT '[]'::jsonb,
    commercial_requirements JSONB   DEFAULT '[]'::jsonb,
    legal_requirements      JSONB   DEFAULT '[]'::jsonb,
    
    -- Обязательные документы
    required_documents      JSONB   DEFAULT '[]'::jsonb,
    
    -- Ключевые даты
    key_deadlines           JSONB   DEFAULT '[]'::jsonb,
    
    -- Риски
    risks                   JSONB   DEFAULT '[]'::jsonb,
    
    -- Gap Analysis
    missing_info_from_tender JSONB  DEFAULT '[]'::jsonb,
    missing_company_data    JSONB   DEFAULT '[]'::jsonb,
    
    -- Технические метаданные
    llm_model               VARCHAR(100),           -- 'gemini-1.5-pro' | 'gpt-4o'
    input_tokens            INTEGER,
    output_tokens           INTEGER,
    processing_time_ms      INTEGER,
    
    error_message           TEXT,
    
    -- Метаданные
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- Индексы
CREATE INDEX idx_analysis_project_id ON analysis_results(project_id);
CREATE INDEX idx_analysis_company_id ON analysis_results(company_id);
-- FIX #3: Partial index для быстрого доступа к текущему анализу
CREATE UNIQUE INDEX idx_analysis_current ON analysis_results(project_id)
    WHERE is_current = true;  -- Гарантирует уникальность текущего анализа на уровне индекса
-- GIN индекс для поиска по JSONB
CREATE INDEX idx_analysis_risks_gin ON analysis_results USING gin(risks);

-- RLS
ALTER TABLE analysis_results ENABLE ROW LEVEL SECURITY;

CREATE POLICY "analysis_company_access" ON analysis_results
    FOR ALL
    USING (company_id = (auth.jwt() ->> 'company_id')::UUID);
```

**JSONB структуры:**

```json
// technical_requirements (массив)
[
  {
    "id": "req_001",
    "text": "Срок строительства не более 18 месяцев",
    "category": "timeline",
    "is_mandatory": true,
    "source_section": "3.2. Сроки реализации",
    "source_page": 12
  }
]

// risks (массив)
[
  {
    "id": "risk_001",
    "description": "Требование о наличии опыта 10+ лет может быть недостижимым",
    "severity": "High",
    "risk_type": "qualification",
    "mitigation": "Уточнить у заказчика возможность партнёрства",
    "source_section": "4.1. Квалификационные требования"
  }
]

// key_deadlines (массив)
[
  {
    "event": "Срок подачи заявки",
    "date": "2026-08-15",
    "is_hard_deadline": true,
    "source_section": "1.4. Сроки"
  }
]
```

---

### 2.6 chat_sessions (Сессии AI-чата)

```sql
CREATE TABLE chat_sessions (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID            NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
    company_id      UUID            NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    
    -- Контекст
    clarification_context JSONB    DEFAULT '{}'::jsonb,
    -- Накопленные ответы пользователя
    
    -- Статус
    is_complete     BOOLEAN         NOT NULL DEFAULT false,
    -- true = достаточно данных для генерации
    
    -- Метаданные
    message_count   INTEGER         NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- RLS
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "chat_sessions_company_access" ON chat_sessions
    FOR ALL
    USING (company_id = (auth.jwt() ->> 'company_id')::UUID);
```

**JSONB структура clarification_context:**

```json
{
  "company_experience": "15 лет в строительстве промышленных объектов",
  "company_certifications": ["ISO 9001:2015", "ГОСТ Р ИСО 14001"],
  "proposed_price": 450000000,
  "price_currency": "KZT",
  "payment_terms": "30% аванс, 70% по завершении",
  "warranty_period": "24 месяца",
  "proposed_solution": "Применение технологии монолитного строительства с...",
  "custom_answers": {
    "Есть ли у вас опыт в строительстве нефтехимических объектов?": "Да, 3 объекта за последние 5 лет"
  },
  "is_complete": true
}
```

---

### 2.7 chat_messages (Сообщения чата)

```sql
CREATE TABLE chat_messages (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID            NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    project_id      UUID            NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    company_id      UUID            NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    
    -- Сообщение
    role            VARCHAR(20)     NOT NULL,
    -- 'assistant' (AI) | 'user' (пользователь) | 'system'
    
    content         TEXT            NOT NULL,
    
    -- Тип сообщения
    message_type    VARCHAR(50)     NOT NULL DEFAULT 'text',
    -- 'question' | 'answer' | 'info' | 'completion' | 'text'
    
    -- Метаданные
    related_gap_id  VARCHAR(100),                   -- К какому gap относится вопрос
    llm_tokens      INTEGER,                        -- Токены использованные для этого сообщения
    
    -- Метаданные
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- Индексы
CREATE INDEX idx_chat_messages_session ON chat_messages(session_id, created_at);
CREATE INDEX idx_chat_messages_project ON chat_messages(project_id);

-- RLS
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "chat_messages_company_access" ON chat_messages
    FOR ALL
    USING (company_id = (auth.jwt() ->> 'company_id')::UUID);
```

---

### 2.8 generated_documents (Сгенерированные документы)

```sql
CREATE TABLE generated_documents (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID            NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    company_id      UUID            NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    created_by      UUID            NOT NULL REFERENCES public.users(id),
    
    -- Тип документа
    doc_type        VARCHAR(50)     NOT NULL,
    -- 'commercial_proposal' | 'tech_spec' | 'cover_letter'
    
    -- Версия
    version         INTEGER         NOT NULL DEFAULT 1,
    is_current      BOOLEAN         NOT NULL DEFAULT true,
    
    -- Контент (HTML для редактора)
    content_html    TEXT,                           -- Rich-text HTML версия
    content_json    JSONB,                          -- Структурированная версия (sections)
    
    -- Метаданные генерации
    generation_status VARCHAR(50)   NOT NULL DEFAULT 'pending',
    -- 'pending' | 'generating' | 'partially_generated' | 'completed' | 'failed'
    -- FIX #7: 'partially_generated' — часть секций сгенерирована, можно resume

    prompt_version  VARCHAR(20),                    -- FIX #11: версия промпта которым сгенерирован документ

    llm_model       VARCHAR(100),
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    generation_time_ms INTEGER,

    error_message   TEXT,
    
    -- Пользовательская обратная связь
    user_rating     SMALLINT,                       -- 1 (👎) или 5 (👍)
    user_feedback   TEXT,                           -- Текстовый комментарий
    feedback_reason VARCHAR(100),                   -- Причина негативной оценки
    
    -- Метаданные
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- Индексы
CREATE INDEX idx_gendocs_project_id ON generated_documents(project_id);
CREATE INDEX idx_gendocs_company_id ON generated_documents(company_id);
CREATE INDEX idx_gendocs_type_current ON generated_documents(project_id, doc_type, is_current)
    WHERE is_current = true;
-- FIX #22: Индекс на created_by для аудита действий пользователя
CREATE INDEX idx_gendocs_created_by ON generated_documents(created_by);

-- RLS
ALTER TABLE generated_documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY "gendocs_company_access" ON generated_documents
    FOR ALL
    USING (company_id = (auth.jwt() ->> 'company_id')::UUID);
```

**JSONB структура content_json:**

```json
{
  "doc_type": "commercial_proposal",
  "title": "Коммерческое предложение № КП-2026-001",
  "sections": [
    {
      "id": "section_1",
      "order": 1,
      "type": "title_page",
      "title": "Титульный лист",
      "content": "<h1>Коммерческое предложение</h1>..."
    },
    {
      "id": "section_2",
      "order": 2,
      "type": "intro",
      "title": "Вводная часть",
      "content": "<p>Уважаемые коллеги...</p>"
    }
  ],
  "metadata": {
    "generated_at": "2026-07-09T10:00:00Z",
    "template": "standard_kz_v1",
    "word_count": 2450
  }
}
```

---

### 2.9 document_exports (Экспортированные файлы)

```sql
CREATE TABLE document_exports (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    generated_doc_id UUID           NOT NULL REFERENCES generated_documents(id) ON DELETE CASCADE,
    project_id      UUID            NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    company_id      UUID            NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    exported_by     UUID            NOT NULL REFERENCES public.users(id),
    
    -- Формат
    format          VARCHAR(10)     NOT NULL,        -- 'docx' | 'pdf'
    
    -- Файл
    storage_path    TEXT            NOT NULL,        -- Путь в Storage
    file_size_bytes BIGINT,
    filename        VARCHAR(500),                   -- Имя скачанного файла
    
    -- Статус генерации файла
    export_status   VARCHAR(50)     NOT NULL DEFAULT 'pending',
    -- 'pending' | 'generating' | 'ready' | 'failed'
    
    download_url    TEXT,                           -- Подписанный URL для скачивания
    url_expires_at  TIMESTAMPTZ,                    -- Когда истекает URL
    
    error_message   TEXT,
    
    -- Метаданные
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- Индексы
CREATE INDEX idx_exports_gendoc_id ON document_exports(generated_doc_id);
CREATE INDEX idx_exports_company_id ON document_exports(company_id);

-- RLS
ALTER TABLE document_exports ENABLE ROW LEVEL SECURITY;

CREATE POLICY "exports_company_access" ON document_exports
    FOR ALL
    USING (company_id = (auth.jwt() ->> 'company_id')::UUID);
```

---

### 2.10 document_templates (Шаблоны документов)

```sql
CREATE TABLE document_templates (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      UUID            REFERENCES companies(id) ON DELETE CASCADE,
    -- NULL = системный шаблон, UUID = шаблон компании
    
    -- Информация
    name            VARCHAR(255)    NOT NULL,
    doc_type        VARCHAR(50)     NOT NULL,        -- 'commercial_proposal' | 'tech_spec' | 'cover_letter'
    description     TEXT,
    
    -- Контент шаблона
    template_html   TEXT,                           -- HTML шаблон с переменными {{variable}}
    template_json   JSONB,                          -- Структура секций
    
    -- Метаданные
    is_system       BOOLEAN         NOT NULL DEFAULT false,   -- Системный или пользовательский
    is_active       BOOLEAN         NOT NULL DEFAULT true,
    language        VARCHAR(10)     NOT NULL DEFAULT 'ru',
    version         INTEGER         NOT NULL DEFAULT 1,
    
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- Индексы
CREATE INDEX idx_templates_company ON document_templates(company_id, doc_type);
CREATE INDEX idx_templates_system ON document_templates(doc_type, is_system) WHERE is_system = true;

-- RLS: системные шаблоны видны всем, компанейские - только своей компании
ALTER TABLE document_templates ENABLE ROW LEVEL SECURITY;

CREATE POLICY "templates_access" ON document_templates
    FOR SELECT
    USING (
        is_system = true
        OR company_id = (auth.jwt() ->> 'company_id')::UUID
    );

CREATE POLICY "templates_modify" ON document_templates
    FOR ALL
    USING (company_id = (auth.jwt() ->> 'company_id')::UUID);
```

---

### 2.11 audit_logs (Аудит-лог)

```sql
CREATE TABLE audit_logs (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      UUID            NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    user_id         UUID            REFERENCES public.users(id) ON DELETE SET NULL,
    
    -- Действие
    action          VARCHAR(100)    NOT NULL,
    -- 'project.created' | 'document.uploaded' | 'analysis.completed'
    -- 'generation.started' | 'generation.completed' | 'export.created'
    -- 'user.login' | 'user.logout' | 'settings.updated'
    
    -- Объект действия
    resource_type   VARCHAR(50),                    -- 'project' | 'document' | 'user'
    resource_id     UUID,
    
    -- Детали
    metadata        JSONB           DEFAULT '{}'::jsonb,
    ip_address      INET,
    user_agent      TEXT,
    
    -- Результат
    success         BOOLEAN         NOT NULL DEFAULT true,
    error_message   TEXT,
    
    -- Метаданные
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- Индексы
CREATE INDEX idx_audit_company ON audit_logs(company_id, created_at DESC);
CREATE INDEX idx_audit_user ON audit_logs(user_id, created_at DESC);
CREATE INDEX idx_audit_action ON audit_logs(company_id, action, created_at DESC);

-- RLS
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "audit_company_access" ON audit_logs
    FOR SELECT
    USING (company_id = (auth.jwt() ->> 'company_id')::UUID);
    -- INSERT только через service role (backend)
```

---

### 2.12 ai_usage_logs (Лог использования AI)

```sql
CREATE TABLE ai_usage_logs (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      UUID            NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    user_id         UUID            REFERENCES public.users(id),
    project_id      UUID            REFERENCES projects(id) ON DELETE SET NULL,
    
    -- AI операция
    operation       VARCHAR(100)    NOT NULL,
    -- 'document_analysis' | 'chat_message' | 'generation_kp' | 'generation_ts' | 'generation_letter'
    
    -- LLM метрики
    llm_model       VARCHAR(100)    NOT NULL,
    input_tokens    INTEGER         NOT NULL,
    output_tokens   INTEGER         NOT NULL,
    total_tokens    INTEGER         GENERATED ALWAYS AS (input_tokens + output_tokens) STORED,
    
    -- Стоимость (в центах USD)
    cost_usd_cents  NUMERIC(10, 4),
    
    -- Производительность
    duration_ms     INTEGER,
    
    -- Статус
    success         BOOLEAN         NOT NULL DEFAULT true,
    error_type      VARCHAR(100),
    
    -- Метаданные
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- Индексы
CREATE INDEX idx_ai_usage_company ON ai_usage_logs(company_id, created_at DESC);
CREATE INDEX idx_ai_usage_billing ON ai_usage_logs(company_id, created_at DESC, success);

-- FIX #14: Партиционирование по месяцам АКТИВИРОВАНО (не закомментировано).
-- Причина: при 100+ компаниях × 20 тендеров × 5 AI-операций = 100k записей/мес.
-- Через 6 месяцев — 600k строк; company_usage_stats VIEW начнёт таймаутить.
-- ОБЯЗАТЕЛЬНО создавать с партиционированием с первого дня — ретрофит болезненен.
--
-- DDL с партиционированием:
CREATE TABLE ai_usage_logs_partitioned (
    -- (те же поля что выше)
) PARTITION BY RANGE (created_at);

-- Партиции создаются заранее или автоматически через pg_partman:
-- Пример ручного создания:
CREATE TABLE ai_usage_logs_2026_07
    PARTITION OF ai_usage_logs_partitioned
    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');

CREATE TABLE ai_usage_logs_2026_08
    PARTITION OF ai_usage_logs_partitioned
    FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');

-- Рекомендуется: pg_partman для автоматического создания партиций
-- CREATE EXTENSION pg_partman;
-- SELECT partman.create_parent('public.ai_usage_logs', 'created_at', 'native', 'monthly');
```

---

## 3. Functions и Triggers

### 3.1 update_updated_at() — общий триггер

```sql
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Применяется к таблицам: companies, users, projects, documents,
-- analysis_results, chat_sessions, generated_documents, document_templates
```

### 3.2 increment_chat_message_count()

```sql
CREATE OR REPLACE FUNCTION increment_chat_message_count()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE chat_sessions
    SET message_count = message_count + 1
    WHERE id = NEW.session_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER chat_message_counter
    AFTER INSERT ON chat_messages
    FOR EACH ROW EXECUTE FUNCTION increment_chat_message_count();
```

### 3.3 deactivate_previous_document_version()

```sql
CREATE OR REPLACE FUNCTION deactivate_previous_document_version()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_current = true THEN
        UPDATE documents
        SET is_current = false
        WHERE project_id = NEW.project_id
          AND id != NEW.id
          AND is_current = true;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER ensure_single_current_document
    AFTER INSERT OR UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION deactivate_previous_document_version();
```

### 3.5 deactivate_previous_analysis_version() — FIX #3

```sql
-- FIX #3: Аналог trigger для documents — обеспечивает единственный is_current анализ на проект.
-- При retry анализа (INSERT новой записи) предыдущая автоматически деактивируется.
CREATE OR REPLACE FUNCTION deactivate_previous_analysis_version()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_current = true THEN
        UPDATE analysis_results
        SET is_current = false
        WHERE project_id = NEW.project_id
          AND id != NEW.id
          AND is_current = true;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER ensure_single_current_analysis
    AFTER INSERT OR UPDATE ON analysis_results
    FOR EACH ROW EXECUTE FUNCTION deactivate_previous_analysis_version();
```

### 3.4 log_project_status_change()

```sql
CREATE OR REPLACE FUNCTION log_project_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status != NEW.status THEN
        INSERT INTO audit_logs (company_id, user_id, action, resource_type, resource_id, metadata)
        VALUES (
            NEW.company_id,
            auth.uid(),
            'project.status_changed',
            'project',
            NEW.id,
            jsonb_build_object('from', OLD.status, 'to', NEW.status)
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER track_project_status
    AFTER UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION log_project_status_change();
```

---

## 4. Views (Представления)

### 4.1 project_summary (Агрегированное представление проектов)

```sql
CREATE VIEW project_summary AS
SELECT
    p.id,
    p.company_id,
    p.name,
    p.customer_name,
    p.status,
    p.tender_type,
    p.complexity,
    p.deadline_at,
    p.created_at,
    p.updated_at,
    
    -- Документ
    d.filename AS document_filename,
    d.processing_status AS document_status,
    d.page_count AS document_pages,
    
    -- Анализ
    ar.status AS analysis_status,
    ar.complexity_level,
    jsonb_array_length(ar.risks) AS risk_count,
    jsonb_array_length(ar.technical_requirements) AS requirement_count,
    
    -- Сгенерированные документы
    COUNT(DISTINCT gd.id) FILTER (WHERE gd.doc_type = 'commercial_proposal' AND gd.is_current)
        AS has_commercial_proposal,
    COUNT(DISTINCT gd.id) FILTER (WHERE gd.doc_type = 'tech_spec' AND gd.is_current)
        AS has_tech_spec,
    COUNT(DISTINCT gd.id) FILTER (WHERE gd.doc_type = 'cover_letter' AND gd.is_current)
        AS has_cover_letter,
    
    -- Чат
    cs.is_complete AS chat_complete,
    cs.message_count,
    
    -- Пользователь
    u.full_name AS created_by_name

FROM projects p
LEFT JOIN documents d ON d.project_id = p.id AND d.is_current = true
LEFT JOIN analysis_results ar ON ar.project_id = p.id
LEFT JOIN generated_documents gd ON gd.project_id = p.id
LEFT JOIN chat_sessions cs ON cs.project_id = p.id
LEFT JOIN public.users u ON u.id = p.created_by
GROUP BY p.id, d.id, ar.id, cs.id, u.id;
```

### 4.2 company_usage_stats

```sql
CREATE VIEW company_usage_stats AS
SELECT
    company_id,
    DATE_TRUNC('month', created_at) AS month,
    
    COUNT(*) AS total_operations,
    SUM(input_tokens) AS total_input_tokens,
    SUM(output_tokens) AS total_output_tokens,
    SUM(total_tokens) AS total_tokens,
    SUM(cost_usd_cents) AS total_cost_usd_cents,
    
    COUNT(*) FILTER (WHERE operation = 'document_analysis') AS analysis_count,
    COUNT(*) FILTER (WHERE operation LIKE 'generation%') AS generation_count,
    COUNT(*) FILTER (WHERE success = false) AS error_count

FROM ai_usage_logs
GROUP BY company_id, DATE_TRUNC('month', created_at);
```

---

## 5. Storage (Supabase Storage)

### Бакеты (Buckets)

```
binom-ai-storage/
├── company-assets/          # Логотипы, брендинг (public read, private write)
│   └── {company_id}/
│       └── logo.{ext}
│
├── tender-documents/        # Загруженные ТЗ (private - только owner)
│   └── {company_id}/
│       └── {project_id}/
│           └── {doc_id}_{filename}
│
├── extracted-texts/         # FIX #6: Извлечённый текст ТЗ (private)
│   └── {company_id}/        # Хранится как .txt, а не в PostgreSQL TEXT поле
│       └── {project_id}/    # Исключает TOAST bloat при 500+ документах
│           └── {doc_id}.txt # Загружается в память только при AI-вызове
│
└── exported-documents/      # Экспортированные DOCX/PDF (temp URLs)
    └── {company_id}/
        └── {project_id}/
            └── {export_id}_{doc_type}.{format}
```

### Storage Policies

```sql
-- company-assets: чтение публичное, запись только своя компания
CREATE POLICY "company_assets_read" ON storage.objects
    FOR SELECT USING (bucket_id = 'company-assets');

CREATE POLICY "company_assets_write" ON storage.objects
    FOR INSERT WITH CHECK (
        bucket_id = 'company-assets'
        AND (storage.foldername(name))[1] = (auth.jwt() ->> 'company_id')
    );

-- tender-documents: только своя компания
CREATE POLICY "tender_docs_access" ON storage.objects
    FOR ALL USING (
        bucket_id = 'tender-documents'
        AND (storage.foldername(name))[1] = (auth.jwt() ->> 'company_id')
    );
```

---

## 6. Миграции

### Порядок создания таблиц (зависимости)

```
1. companies
2. auth.users (автоматически Supabase)
3. public.users
4. projects
5. documents
6. analysis_results
7. chat_sessions
8. chat_messages
9. document_templates
10. generated_documents
11. document_exports
12. audit_logs
13. ai_usage_logs (партиционированная)
14. prompt_versions               ← FIX #11: таблица версий промптов
15. Views: project_summary, company_usage_stats
16. Triggers: update_updated_at, chat_message_counter, deactivate_previous_document_version, deactivate_previous_analysis_version
17. Storage buckets + policies
18. Seed data: system templates, initial prompt versions (v1)
```

> **FIX #25 — Выбор migration tool:** использовать **только Supabase migrations** (`supabase db push` / `supabase migration new`). Не использовать Alembic одновременно — два инструмента для одной БД создают конфликты. Supabase migrations лучше интегрированы с RLS, Auth hooks и Storage policies.

### Команда начальной миграции

```bash
supabase db push
# или
psql -h db.xxx.supabase.co -U postgres -d postgres -f migrations/001_initial_schema.sql
```

---

## 7. Индексирование и производительность

### Стратегия индексов

| Таблица | Индекс | Назначение |
|---------|--------|-----------|
| projects | (company_id, status) | Фильтрация по компании и статусу |
| projects | (company_id, created_at DESC) | Сортировка списка проектов |
| documents | (project_id, is_current) | Быстрый доступ к текущему документу |
| chat_messages | (session_id, created_at) | Загрузка истории чата |
| analysis_results | GIN на risks, requirements | Поиск по JSONB |
| ai_usage_logs | (company_id, created_at DESC) | Биллинг и статистика |

### Оценка объёма данных (1000 компаний, год работы)

| Таблица | Строк | Объём |
|---------|-------|-------|
| companies | 1,000 | ~5 MB |
| users | 3,000 | ~15 MB |
| projects | 50,000 | ~200 MB |
| documents | 50,000 | ~500 MB (метаданные) |
| documents (files) | 50,000 | ~50 GB (Storage) |
| analysis_results | 50,000 | ~5 GB (JSONB) |
| chat_messages | 500,000 | ~2 GB |
| generated_documents | 150,000 | ~15 GB |
| ai_usage_logs | 500,000 | ~1 GB |

---

## 8. JWT Claims (Custom Claims)

Supabase позволяет добавлять кастомные claims в JWT токен. Для BINOM AI:

```sql
-- Hook для добавления company_id в JWT
CREATE OR REPLACE FUNCTION auth.custom_access_token_hook(event jsonb)
RETURNS jsonb AS $$
DECLARE
    claims jsonb;
    user_company_id uuid;
    user_role varchar;
BEGIN
    -- Получить company_id и роль пользователя
    SELECT company_id, role INTO user_company_id, user_role
    FROM public.users
    WHERE id = (event ->> 'user_id')::uuid;
    
    claims := event -> 'claims';
    
    -- Добавить в JWT
    claims := jsonb_set(claims, '{company_id}', to_jsonb(user_company_id));
    claims := jsonb_set(claims, '{user_role}', to_jsonb(user_role));
    
    RETURN jsonb_set(event, '{claims}', claims);
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;
```

**Результирующий JWT payload:**
```json
{
  "sub": "user-uuid",
  "email": "user@company.kz",
  "company_id": "company-uuid",
  "user_role": "admin",
  "exp": 1234567890
}
```

---

*Документ подготовлен командой BINOM AI. Database Schema v1.0 — утверждён.*  
*Следующий документ: [API Specification.md](./API%20Specification.md)*
