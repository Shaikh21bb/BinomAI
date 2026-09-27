-- A fingerprint lets the API reopen an identical PDF without retaining its bytes.
-- Multiple runs deliberately share the same fingerprint so refreshes remain in history.
ALTER TABLE public.quick_check_reports
    ADD COLUMN IF NOT EXISTS pdf_sha256 varchar(64);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'quick_check_reports_pdf_sha256_check'
          AND conrelid = 'public.quick_check_reports'::regclass
    ) THEN
        ALTER TABLE public.quick_check_reports
            ADD CONSTRAINT quick_check_reports_pdf_sha256_check
            CHECK (pdf_sha256 IS NULL OR pdf_sha256 ~ '^[0-9a-f]{64}$');
    END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_quick_check_reports_owner_pdf_created
    ON public.quick_check_reports(created_by, pdf_sha256, created_at DESC)
    WHERE pdf_sha256 IS NOT NULL;
