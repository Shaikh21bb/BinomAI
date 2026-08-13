-- ============================================================
-- 20260811000000_analysis_and_generation.sql
-- Tables: analysis_results, generated_documents
-- (local) Applied directly to binom_postgres via psql.
-- ============================================================

-- ------------------------------------------------------------
-- 1. analysis_results
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analysis_results (
    id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id                  uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    document_id                 uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    company_id                  uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    status                      varchar(50) NOT NULL DEFAULT 'pending',
    is_current                  boolean NOT NULL DEFAULT true,
    prompt_version              varchar(20) NOT NULL DEFAULT 'v1',
    error_message               text,
    executive_summary           text,
    tender_type                 varchar(255),
    complexity_level            varchar(50),
    estimated_duration_days     integer,
    technical_requirements      jsonb,
    commercial_requirements     jsonb,
    legal_requirements          jsonb,
    required_documents          jsonb,
    key_deadlines               jsonb,
    risks                       jsonb,
    missing_info_from_tender    jsonb,
    missing_company_data        jsonb,
    llm_model                   varchar(255),
    input_tokens                integer,
    output_tokens               integer,
    processing_time_ms          integer,
    created_at                  timestamptz NOT NULL DEFAULT now(),
    updated_at                  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_analysis_results_project   ON analysis_results(project_id);
CREATE INDEX IF NOT EXISTS idx_analysis_results_current   ON analysis_results(project_id, is_current);

-- Keep only one current analysis per project
CREATE OR REPLACE FUNCTION ensure_single_current_analysis() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_current THEN
        UPDATE analysis_results SET is_current = false
        WHERE project_id = NEW.project_id AND id <> NEW.id AND is_current = true;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_single_current_analysis ON analysis_results;
CREATE TRIGGER trg_single_current_analysis
AFTER INSERT OR UPDATE OF is_current ON analysis_results
FOR EACH ROW EXECUTE FUNCTION ensure_single_current_analysis();

-- ------------------------------------------------------------
-- 2. generated_documents
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS generated_documents (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    company_id          uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    doc_type            varchar(50) NOT NULL,
    version             integer NOT NULL DEFAULT 1,
    title               varchar(500) NOT NULL,
    content_md          text,
    content_html        text,
    generation_status   varchar(50) NOT NULL DEFAULT 'generating',
    error_message       text,
    llm_model           varchar(255),
    exported_formats    jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_generated_documents_project ON generated_documents(project_id, doc_type, version);