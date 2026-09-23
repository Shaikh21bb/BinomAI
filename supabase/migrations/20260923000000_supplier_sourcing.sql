-- BINOM AI: supplier quote comparison and sourcing plan
-- Additive and tenant-scoped. No quote is treated as verified unless a user
-- enters or imports it; discovery results stay on product_search_items.

CREATE TABLE IF NOT EXISTS product_search_items (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    company_id      uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    product_name    varchar(500) NOT NULL,
    specs           text,
    unit            varchar(50),
    quantity        double precision,
    source_section  varchar(255),
    status          varchar(50) NOT NULL DEFAULT 'pending',
    error_message   text,
    results         jsonb NOT NULL DEFAULT '[]'::jsonb,
    best_match      jsonb,
    search_region   varchar(255),
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_product_search_items_project ON product_search_items(project_id);
CREATE INDEX IF NOT EXISTS idx_product_search_items_company ON product_search_items(company_id);

ALTER TABLE product_search_items ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS product_search_items_company_access ON product_search_items;
DO $$
BEGIN
    -- Local Docker development uses plain PostgreSQL without Supabase's auth schema.
    -- The backend still scopes every query by company_id; Supabase deployments also
    -- receive the database-level tenant policy below.
    IF to_regprocedure('auth.jwt()') IS NOT NULL THEN
        EXECUTE $policy$
            CREATE POLICY product_search_items_company_access ON product_search_items
                FOR ALL USING (company_id = (auth.jwt() ->> 'company_id')::uuid)
                WITH CHECK (company_id = (auth.jwt() ->> 'company_id')::uuid)
        $policy$;
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS sourcing_plans (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    company_id          uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    target_margin_pct   numeric(5,2) NOT NULL DEFAULT 15 CHECK (target_margin_pct >= 0 AND target_margin_pct < 95),
    base_currency       varchar(3) NOT NULL DEFAULT 'KZT',
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_sourcing_plans_project UNIQUE (project_id)
);

CREATE INDEX IF NOT EXISTS idx_sourcing_plans_company ON sourcing_plans(company_id);

ALTER TABLE sourcing_plans ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS sourcing_plans_company_access ON sourcing_plans;
DO $$
BEGIN
    IF to_regprocedure('auth.jwt()') IS NOT NULL THEN
        EXECUTE $policy$
            CREATE POLICY sourcing_plans_company_access ON sourcing_plans
                FOR ALL USING (company_id = (auth.jwt() ->> 'company_id')::uuid)
                WITH CHECK (company_id = (auth.jwt() ->> 'company_id')::uuid)
        $policy$;
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS supplier_offers (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id              uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    company_id              uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    item_id                 uuid REFERENCES product_search_items(id) ON DELETE SET NULL,
    created_by              uuid NOT NULL REFERENCES public.users(id),
    supplier_name           varchar(500) NOT NULL,
    supplier_bin            varchar(12),
    supplier_contact        varchar(500),
    original_item_name      varchar(500) NOT NULL,
    normalized_item_name    varchar(500),
    original_unit           varchar(80),
    normalized_unit         varchar(30),
    quoted_quantity         numeric(18,4),
    unit_price              numeric(18,4) NOT NULL CHECK (unit_price >= 0),
    price_quantity          numeric(18,4) NOT NULL DEFAULT 1 CHECK (price_quantity > 0),
    currency                varchar(3) NOT NULL DEFAULT 'KZT',
    exchange_rate_to_kzt    numeric(18,6),
    vat_included            boolean,
    vat_rate                numeric(5,2) CHECK (vat_rate >= 0 AND vat_rate <= 100),
    moq                     numeric(18,4),
    available_quantity      numeric(18,4),
    delivery_cost           numeric(18,2),
    lead_time_days          integer,
    warranty_months         integer,
    certificates            jsonb NOT NULL DEFAULT '[]'::jsonb,
    characteristics         jsonb NOT NULL DEFAULT '{}'::jsonb,
    compliance_status       varchar(30) NOT NULL DEFAULT 'unknown'
                              CHECK (compliance_status IN ('compliant', 'partial', 'noncompliant', 'unknown')),
    compliance_notes        text,
    quote_date              date,
    valid_until             date,
    source_type             varchar(30) NOT NULL DEFAULT 'manual',
    source_filename         varchar(500),
    source_url              text,
    match_status            varchar(30) NOT NULL DEFAULT 'matched'
                              CHECK (match_status IN ('matched', 'needs_review', 'unmatched')),
    match_confidence        numeric(5,4),
    is_selected             boolean NOT NULL DEFAULT false,
    selection_note          text,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_supplier_offers_project ON supplier_offers(project_id);
CREATE INDEX IF NOT EXISTS idx_supplier_offers_company ON supplier_offers(company_id);
CREATE INDEX IF NOT EXISTS idx_supplier_offers_item ON supplier_offers(item_id);
CREATE INDEX IF NOT EXISTS idx_supplier_offers_review ON supplier_offers(project_id, match_status);
CREATE UNIQUE INDEX IF NOT EXISTS uq_supplier_offers_selected_item
    ON supplier_offers(item_id)
    WHERE is_selected AND item_id IS NOT NULL;

ALTER TABLE supplier_offers ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS supplier_offers_company_access ON supplier_offers;
DO $$
BEGIN
    IF to_regprocedure('auth.jwt()') IS NOT NULL THEN
        EXECUTE $policy$
            CREATE POLICY supplier_offers_company_access ON supplier_offers
                FOR ALL USING (company_id = (auth.jwt() ->> 'company_id')::uuid)
                WITH CHECK (company_id = (auth.jwt() ->> 'company_id')::uuid)
        $policy$;
    END IF;
END
$$;

DROP TRIGGER IF EXISTS set_product_search_items_updated_at ON product_search_items;
CREATE TRIGGER set_product_search_items_updated_at
    BEFORE UPDATE ON product_search_items
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS set_sourcing_plans_updated_at ON sourcing_plans;
CREATE TRIGGER set_sourcing_plans_updated_at
    BEFORE UPDATE ON sourcing_plans
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS set_supplier_offers_updated_at ON supplier_offers;
CREATE TRIGGER set_supplier_offers_updated_at
    BEFORE UPDATE ON supplier_offers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
