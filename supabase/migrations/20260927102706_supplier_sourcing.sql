-- Supplier sourcing and price comparison.
-- Additive/idempotent so existing product discovery data is preserved.

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = ''
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TABLE IF NOT EXISTS product_search_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    product_name varchar(500) NOT NULL,
    specs text,
    unit varchar(50),
    quantity double precision,
    source_section varchar(255),
    status varchar(50) NOT NULL DEFAULT 'pending',
    error_message text,
    results jsonb NOT NULL DEFAULT '[]'::jsonb,
    best_match jsonb,
    search_region varchar(255),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE product_search_items ADD COLUMN IF NOT EXISTS normalized_name varchar(500);
ALTER TABLE product_search_items ADD COLUMN IF NOT EXISTS normalized_unit varchar(50);
ALTER TABLE product_search_items ADD COLUMN IF NOT EXISTS required_certificates jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE product_search_items ADD COLUMN IF NOT EXISTS warranty_required boolean NOT NULL DEFAULT false;
ALTER TABLE product_search_items ADD COLUMN IF NOT EXISTS desired_delivery_date date;
ALTER TABLE product_search_items ADD COLUMN IF NOT EXISTS source_type varchar(30) NOT NULL DEFAULT 'document';
ALTER TABLE product_search_items ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;

CREATE INDEX IF NOT EXISTS idx_product_search_project ON product_search_items(project_id);
CREATE INDEX IF NOT EXISTS idx_product_search_company ON product_search_items(company_id);
CREATE INDEX IF NOT EXISTS idx_product_search_active ON product_search_items(project_id, is_active);

CREATE TABLE IF NOT EXISTS supplier_offers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    product_item_id uuid REFERENCES product_search_items(id) ON DELETE SET NULL,
    created_by uuid NOT NULL REFERENCES public.users(id),
    supplier_name varchar(500) NOT NULL,
    supplier_bin varchar(12),
    supplier_contact varchar(500),
    supplier_sku varchar(255),
    product_name varchar(500) NOT NULL,
    quoted_unit varchar(50),
    offered_quantity numeric(18,4),
    unit_conversion_factor numeric(18,6),
    unit_price numeric(18,4),
    total_price numeric(18,2),
    currency varchar(3) NOT NULL DEFAULT 'KZT',
    exchange_rate_to_kzt numeric(18,6),
    exchange_rate_date date,
    vat_included boolean,
    vat_rate numeric(6,3),
    min_order_quantity numeric(18,4),
    availability_status varchar(30) NOT NULL DEFAULT 'unknown',
    available_quantity numeric(18,4),
    delivery_cost numeric(18,2),
    delivery_days integer,
    warranty_months integer,
    certificates jsonb NOT NULL DEFAULT '[]'::jsonb,
    specification_compliant boolean,
    compliance_notes text,
    quote_date date,
    price_valid_until date,
    source_type varchar(30) NOT NULL DEFAULT 'manual',
    source_reference text,
    source_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    match_status varchar(30) NOT NULL DEFAULT 'confirmed',
    match_candidates jsonb NOT NULL DEFAULT '[]'::jsonb,
    notes text,
    is_selected boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT supplier_offers_price_present CHECK (unit_price IS NOT NULL OR total_price IS NOT NULL),
    CONSTRAINT supplier_offers_nonnegative_price CHECK (
        (unit_price IS NULL OR unit_price >= 0) AND (total_price IS NULL OR total_price >= 0)
    )
);

CREATE INDEX IF NOT EXISTS idx_supplier_offers_project ON supplier_offers(project_id);
CREATE INDEX IF NOT EXISTS idx_supplier_offers_company ON supplier_offers(company_id);
CREATE INDEX IF NOT EXISTS idx_supplier_offers_item ON supplier_offers(product_item_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_supplier_offer_selected_item
    ON supplier_offers(product_item_id) WHERE is_selected = true AND product_item_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS sourcing_settings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    updated_by uuid NOT NULL REFERENCES public.users(id),
    target_margin_percent numeric(6,3) NOT NULL DEFAULT 15,
    base_currency varchar(3) NOT NULL DEFAULT 'KZT',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT sourcing_margin_range CHECK (target_margin_percent >= 0 AND target_margin_percent < 100)
);

CREATE INDEX IF NOT EXISTS idx_sourcing_settings_company ON sourcing_settings(company_id);

ALTER TABLE product_search_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE supplier_offers ENABLE ROW LEVEL SECURITY;
ALTER TABLE sourcing_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "product_search_company_access" ON product_search_items;
CREATE POLICY "product_search_company_access" ON product_search_items
    FOR ALL TO authenticated
    USING (company_id = ((SELECT auth.jwt()) ->> 'company_id')::uuid)
    WITH CHECK (company_id = ((SELECT auth.jwt()) ->> 'company_id')::uuid);

DROP POLICY IF EXISTS "supplier_offers_company_access" ON supplier_offers;
CREATE POLICY "supplier_offers_company_access" ON supplier_offers
    FOR ALL TO authenticated
    USING (company_id = ((SELECT auth.jwt()) ->> 'company_id')::uuid)
    WITH CHECK (company_id = ((SELECT auth.jwt()) ->> 'company_id')::uuid);

DROP POLICY IF EXISTS "sourcing_settings_company_access" ON sourcing_settings;
CREATE POLICY "sourcing_settings_company_access" ON sourcing_settings
    FOR ALL TO authenticated
    USING (company_id = ((SELECT auth.jwt()) ->> 'company_id')::uuid)
    WITH CHECK (company_id = ((SELECT auth.jwt()) ->> 'company_id')::uuid);

DROP TRIGGER IF EXISTS set_product_search_updated_at ON product_search_items;
CREATE TRIGGER set_product_search_updated_at BEFORE UPDATE ON product_search_items
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
DROP TRIGGER IF EXISTS set_supplier_offers_updated_at ON supplier_offers;
CREATE TRIGGER set_supplier_offers_updated_at BEFORE UPDATE ON supplier_offers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
DROP TRIGGER IF EXISTS set_sourcing_settings_updated_at ON sourcing_settings;
CREATE TRIGGER set_sourcing_settings_updated_at BEFORE UPDATE ON sourcing_settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
;
