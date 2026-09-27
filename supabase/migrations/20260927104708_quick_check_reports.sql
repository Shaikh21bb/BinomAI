-- Quick PDF checks are saved as results only; uploaded PDF bytes are never retained.
CREATE TABLE IF NOT EXISTS public.quick_check_reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    created_by uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    filename varchar(500) NOT NULL,
    page_count integer NOT NULL CHECK (page_count BETWEEN 1 AND 60),
    ocr_pages integer NOT NULL DEFAULT 0 CHECK (ocr_pages BETWEEN 0 AND 12),
    total_items integer NOT NULL CHECK (total_items >= 0),
    truncated boolean NOT NULL DEFAULT false,
    items jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(items) = 'array'),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_quick_check_reports_owner_created
    ON public.quick_check_reports(created_by, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_quick_check_reports_company_id
    ON public.quick_check_reports(company_id);

DROP TRIGGER IF EXISTS set_quick_check_reports_updated_at ON public.quick_check_reports;
CREATE TRIGGER set_quick_check_reports_updated_at
    BEFORE UPDATE ON public.quick_check_reports
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

-- These reports are read only by FastAPI over its direct DB connection.
ALTER TABLE public.quick_check_reports ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL PRIVILEGES ON public.quick_check_reports FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL PRIVILEGES ON public.quick_check_reports FROM authenticated;
    END IF;
END;
$$;
