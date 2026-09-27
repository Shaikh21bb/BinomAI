-- Background discovery continues after the browser closes.
ALTER TABLE public.quick_check_reports
    ADD COLUMN IF NOT EXISTS processing_state varchar(20) NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS run_id uuid;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'quick_check_reports_processing_state_check'
          AND conrelid = 'public.quick_check_reports'::regclass
    ) THEN
        ALTER TABLE public.quick_check_reports
            ADD CONSTRAINT quick_check_reports_processing_state_check
            CHECK (processing_state IN ('pending', 'queued', 'running', 'completed', 'error'));
    END IF;
END;
$$;

UPDATE public.quick_check_reports AS report
SET processing_state = 'completed'
WHERE processing_state = 'pending'
  AND NOT EXISTS (
      SELECT 1 FROM jsonb_array_elements(report.items) AS item
      WHERE item->>'state' NOT IN ('ready', 'error')
  );
