-- Supplier quotes and sourcing plans are served exclusively through the FastAPI
-- backend, which applies company and project authorization. Keep the Supabase
-- Data API roles from bypassing that application boundary if default grants are
-- enabled on the project. RLS remains enabled as defense in depth.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL PRIVILEGES ON TABLE
            public.product_search_items,
            public.sourcing_plans,
            public.supplier_offers
        FROM anon;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL PRIVILEGES ON TABLE
            public.product_search_items,
            public.sourcing_plans,
            public.supplier_offers
        FROM authenticated;
    END IF;
END
$$;
