-- BINOM AI: Core Tables Migration

-- Function to handle updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';


-- 1. Companies
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

ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
CREATE POLICY "companies_own_access" ON companies
    FOR ALL USING (id = (auth.jwt() ->> 'company_id')::UUID);

CREATE TRIGGER set_companies_updated_at
    BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- 2. Users (Public)
CREATE TABLE public.users (
    id              UUID            PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
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

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users_own_company" ON public.users
    FOR ALL USING (company_id = (auth.jwt() ->> 'company_id')::UUID);
CREATE POLICY "users_own_profile" ON public.users
    FOR ALL USING (id = auth.uid());

CREATE TRIGGER set_users_updated_at
    BEFORE UPDATE ON public.users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- 3. Projects
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

ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
CREATE POLICY "projects_company_access" ON projects
    FOR ALL USING (company_id = (auth.jwt() ->> 'company_id')::UUID);

CREATE TRIGGER set_projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- 4. Documents
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

ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
CREATE POLICY "documents_company_access" ON documents
    FOR ALL USING (company_id = (auth.jwt() ->> 'company_id')::UUID);

CREATE TRIGGER set_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
