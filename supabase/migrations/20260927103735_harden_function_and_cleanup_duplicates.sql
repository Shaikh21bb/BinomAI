-- Pin the trigger function's object resolution and qualify its table access.
CREATE OR REPLACE FUNCTION public.ensure_single_current_analysis()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
BEGIN
    IF NEW.is_current THEN
        UPDATE public.analysis_results SET is_current = false
        WHERE project_id = NEW.project_id AND id <> NEW.id AND is_current = true;
    END IF;
    RETURN NEW;
END;
$$;

-- Browser roles are intentionally revoked from business tables; remove stale
-- direct-access policies left by historical migrations.
DROP POLICY IF EXISTS product_search_company_access
    ON public.product_search_items;
DROP POLICY IF EXISTS product_search_items_company_access
    ON public.product_search_items;

DO $$
BEGIN
    IF to_regclass('public.sourcing_plans') IS NOT NULL THEN
        EXECUTE 'DROP POLICY IF EXISTS sourcing_plans_company_access ON public.sourcing_plans';
    END IF;
END;
$$;

-- Retain one canonical index for each identical key sequence.
DROP INDEX IF EXISTS public.ix_analysis_results_project_id;
DROP INDEX IF EXISTS public.idx_product_search_items_project;
DROP INDEX IF EXISTS public.idx_product_search_items_company;
