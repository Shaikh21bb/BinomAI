-- BINOM AI: Local Dev Migration (plain Postgres, no Supabase auth/RLS)
-- Adapted from 20260709000000_core_tables.sql

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TABLE companies (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255)    NOT NULL,
    bin_iin         VARCHAR(12)     UNIQUE,
    legal_address   TEXT,
    actual_address  TEXT,
    phone           VARCHAR(20),
    email           VARCHAR(255),
    website         VARCHAR(255),
    logo_url        TEXT,
    specialization  TEXT,
    description     TEXT,
    founded_year    INTEGER,
    employee_count  INTEGER,
    director_name   VARCHAR(255),
    director_title  VARCHAR(255),
    bank_name       VARCHAR(255),
    bank_account    VARCHAR(50),
    bank_bik        VARCHAR(20),
    plan            VARCHAR(50)     NOT NULL DEFAULT 'trial',
    plan_expires_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    is_active       BOOLEAN         NOT NULL DEFAULT true
);

CREATE INDEX idx_companies_bin_iin ON companies(bin_iin);

CREATE TRIGGER set_companies_updated_at
    BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TABLE public.users (
    id              UUID            PRIMARY KEY,
    company_id      UUID            NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    full_name       VARCHAR(255),
    job_title       VARCHAR(255),
    phone           VARCHAR(20),
    avatar_url      TEXT,
    role            VARCHAR(50)     NOT NULL DEFAULT 'user',
    language        VARCHAR(10)     NOT NULL DEFAULT 'ru',
    timezone        VARCHAR(50)     NOT NULL DEFAULT 'Asia/Almaty',
    email_notifications BOOLEAN     NOT NULL DEFAULT true,
    onboarding_completed BOOLEAN    NOT NULL DEFAULT false,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    is_active       BOOLEAN         NOT NULL DEFAULT true
);

CREATE INDEX idx_users_company_id ON public.users(company_id);
CREATE INDEX idx_users_role ON public.users(company_id, role);

CREATE TRIGGER set_users_updated_at
    BEFORE UPDATE ON public.users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TABLE projects (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      UUID            NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    created_by      UUID            NOT NULL REFERENCES public.users(id),
    name            VARCHAR(500)    NOT NULL,
    customer_name   VARCHAR(500),
    customer_bin    VARCHAR(12),
    status          VARCHAR(50)     NOT NULL DEFAULT 'draft',
    deadline_at     TIMESTAMPTZ,
    submission_at   TIMESTAMPTZ,
    tender_type     VARCHAR(100),
    tender_number   VARCHAR(255),
    complexity      VARCHAR(20),
    tags            TEXT[],
    notes           TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX idx_projects_company_id ON projects(company_id);
CREATE INDEX idx_projects_status ON projects(company_id, status);
CREATE INDEX idx_projects_created_at ON projects(company_id, created_at DESC);

CREATE TRIGGER set_projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TABLE documents (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID            NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    company_id      UUID            NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    uploaded_by     UUID            NOT NULL REFERENCES public.users(id),
    filename        VARCHAR(500)    NOT NULL,
    file_size_bytes BIGINT          NOT NULL,
    mime_type       VARCHAR(100)    NOT NULL,
    storage_path    TEXT            NOT NULL,
    extracted_text_path TEXT,
    page_count      INTEGER,
    token_count     INTEGER,
    language        VARCHAR(10),
    processing_status VARCHAR(50)   NOT NULL DEFAULT 'uploading',
    error_message   TEXT,
    doc_title       VARCHAR(500),
    doc_number      VARCHAR(255),
    doc_date        DATE,
    version         INTEGER         NOT NULL DEFAULT 1,
    is_current      BOOLEAN         NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX idx_documents_project_id ON documents(project_id);
CREATE INDEX idx_documents_company_id ON documents(company_id);
CREATE INDEX idx_documents_current ON documents(project_id, is_current) WHERE is_current = true;

CREATE TRIGGER set_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- 5. Chat sessions & messages
CREATE TABLE chat_sessions (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID            NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
    context         JSONB           NOT NULL DEFAULT '{}'::jsonb,
    is_complete     BOOLEAN         NOT NULL DEFAULT false,
    message_count   INTEGER         NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE TABLE chat_messages (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID            NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    role            VARCHAR(10)     NOT NULL,
    content         TEXT            NOT NULL,
    message_type    VARCHAR(20)     NOT NULL DEFAULT 'text',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX idx_chat_messages_project ON chat_messages(project_id, created_at);

CREATE TRIGGER set_chat_messages_updated_at
    BEFORE UPDATE ON chat_messages
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER set_chat_sessions_updated_at
    BEFORE UPDATE ON chat_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();