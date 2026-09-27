-- Remove legacy SQLAlchemy indexes duplicated by the canonical sourcing
-- migration, then cover actor foreign keys used during deletes and joins.

DROP INDEX IF EXISTS public.ix_product_search_items_project_id;
DROP INDEX IF EXISTS public.ix_product_search_items_company_id;

CREATE INDEX IF NOT EXISTS idx_supplier_offers_created_by
    ON public.supplier_offers(created_by);
CREATE INDEX IF NOT EXISTS idx_sourcing_settings_updated_by
    ON public.sourcing_settings(updated_by);
