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
DO $$
BEGIN
    -- Local Docker development uses plain PostgreSQL without Supabase's auth schema.
    -- The backend still scopes every query by company_id; Supabase deployments also
    -- receive the database-level tenant policy below.
    IF to_regprocedure('auth.jwt()') IS NOT NULL
       AND NOT EXISTS (
           SELECT 1 FROM pg_policies
           WHERE schemaname = 'public'
             AND tablename = 'product_search_items'
             AND policyname = 'product_search_items_company_access'
       ) THEN
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

-- Earlier production builds used sourcing_settings. Preserve any values while
-- moving to the schema used by the current backend; keep the legacy table as a
-- rollback aid instead of dropping it during the release.
DO $$
BEGIN
    IF to_regclass('public.sourcing_settings') IS NOT NULL THEN
        EXECUTE $copy$
            INSERT INTO public.sourcing_plans (
                id, project_id, company_id, target_margin_pct, base_currency,
                created_at, updated_at
            )
            SELECT
                id, project_id, company_id, target_margin_percent, base_currency,
                created_at, updated_at
            FROM public.sourcing_settings
            ON CONFLICT (project_id) DO UPDATE SET
                target_margin_pct = EXCLUDED.target_margin_pct,
                base_currency = EXCLUDED.base_currency,
                updated_at = EXCLUDED.updated_at
        $copy$;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_sourcing_plans_company ON sourcing_plans(company_id);

ALTER TABLE sourcing_plans ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
    IF to_regprocedure('auth.jwt()') IS NOT NULL
       AND NOT EXISTS (
           SELECT 1 FROM pg_policies
           WHERE schemaname = 'public'
             AND tablename = 'sourcing_plans'
             AND policyname = 'sourcing_plans_company_access'
       ) THEN
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

-- Upgrade the pre-release supplier_offers table in place. CREATE TABLE IF NOT
-- EXISTS does not add columns to an existing table, so each current field must
-- be added explicitly before indexes and application queries use it.
ALTER TABLE public.supplier_offers
    ADD COLUMN IF NOT EXISTS item_id uuid REFERENCES public.product_search_items(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS original_item_name varchar(500),
    ADD COLUMN IF NOT EXISTS normalized_item_name varchar(500),
    ADD COLUMN IF NOT EXISTS original_unit varchar(80),
    ADD COLUMN IF NOT EXISTS normalized_unit varchar(30),
    ADD COLUMN IF NOT EXISTS quoted_quantity numeric(18,4),
    ADD COLUMN IF NOT EXISTS price_quantity numeric(18,4) NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS moq numeric(18,4),
    ADD COLUMN IF NOT EXISTS lead_time_days integer,
    ADD COLUMN IF NOT EXISTS characteristics jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS compliance_status varchar(30) NOT NULL DEFAULT 'unknown',
    ADD COLUMN IF NOT EXISTS valid_until date,
    ADD COLUMN IF NOT EXISTS source_filename varchar(500),
    ADD COLUMN IF NOT EXISTS source_url text,
    ADD COLUMN IF NOT EXISTS match_confidence numeric(5,4),
    ADD COLUMN IF NOT EXISTS selection_note text;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'supplier_offers'
          AND column_name = 'product_item_id'
    ) THEN
        EXECUTE 'UPDATE public.supplier_offers SET item_id = COALESCE(item_id, product_item_id)';
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'supplier_offers'
          AND column_name = 'product_name'
    ) THEN
        EXECUTE 'UPDATE public.supplier_offers SET original_item_name = COALESCE(original_item_name, product_name)';
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'supplier_offers'
          AND column_name = 'quoted_unit'
    ) THEN
        EXECUTE 'UPDATE public.supplier_offers SET original_unit = COALESCE(original_unit, quoted_unit)';
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'supplier_offers'
          AND column_name = 'offered_quantity'
    ) THEN
        EXECUTE 'UPDATE public.supplier_offers SET quoted_quantity = COALESCE(quoted_quantity, offered_quantity)';
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'supplier_offers'
          AND column_name = 'min_order_quantity'
    ) THEN
        EXECUTE 'UPDATE public.supplier_offers SET moq = COALESCE(moq, min_order_quantity)';
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'supplier_offers'
          AND column_name = 'delivery_days'
    ) THEN
        EXECUTE 'UPDATE public.supplier_offers SET lead_time_days = COALESCE(lead_time_days, delivery_days)';
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'supplier_offers'
          AND column_name = 'price_valid_until'
    ) THEN
        EXECUTE 'UPDATE public.supplier_offers SET valid_until = COALESCE(valid_until, price_valid_until)';
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'supplier_offers'
          AND column_name = 'specification_compliant'
    ) THEN
        EXECUTE $migrate$
            UPDATE public.supplier_offers
            SET compliance_status = CASE
                WHEN specification_compliant IS TRUE THEN 'compliant'
                WHEN specification_compliant IS FALSE THEN 'noncompliant'
                ELSE 'unknown'
            END
        $migrate$;
    END IF;
END
$$;

UPDATE public.supplier_offers
SET original_item_name = COALESCE(NULLIF(original_item_name, ''), 'Legacy offer ' || id::text),
    unit_price = COALESCE(unit_price, 0),
    match_status = CASE
        WHEN match_status IN ('matched', 'needs_review', 'unmatched') THEN match_status
        WHEN match_status IN ('confirmed', 'auto') THEN 'matched'
        WHEN match_status IN ('review', 'ambiguous') THEN 'needs_review'
        ELSE 'unmatched'
    END;

ALTER TABLE public.supplier_offers
    ALTER COLUMN original_item_name SET NOT NULL,
    ALTER COLUMN unit_price SET NOT NULL,
    ALTER COLUMN match_status SET DEFAULT 'matched';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'supplier_offers_unit_price_nonnegative') THEN
        ALTER TABLE public.supplier_offers
            ADD CONSTRAINT supplier_offers_unit_price_nonnegative CHECK (unit_price >= 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'supplier_offers_price_quantity_positive') THEN
        ALTER TABLE public.supplier_offers
            ADD CONSTRAINT supplier_offers_price_quantity_positive CHECK (price_quantity > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'supplier_offers_compliance_status_valid') THEN
        ALTER TABLE public.supplier_offers
            ADD CONSTRAINT supplier_offers_compliance_status_valid
            CHECK (compliance_status IN ('compliant', 'partial', 'noncompliant', 'unknown'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'supplier_offers_match_status_valid') THEN
        ALTER TABLE public.supplier_offers
            ADD CONSTRAINT supplier_offers_match_status_valid
            CHECK (match_status IN ('matched', 'needs_review', 'unmatched'));
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_supplier_offers_project ON supplier_offers(project_id);
CREATE INDEX IF NOT EXISTS idx_supplier_offers_company ON supplier_offers(company_id);
CREATE INDEX IF NOT EXISTS idx_supplier_offers_item ON supplier_offers(item_id);
CREATE INDEX IF NOT EXISTS idx_supplier_offers_review ON supplier_offers(project_id, match_status);
CREATE UNIQUE INDEX IF NOT EXISTS uq_supplier_offers_selected_item
    ON supplier_offers(item_id)
    WHERE is_selected AND item_id IS NOT NULL;

ALTER TABLE supplier_offers ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
    IF to_regprocedure('auth.jwt()') IS NOT NULL
       AND NOT EXISTS (
           SELECT 1 FROM pg_policies
           WHERE schemaname = 'public'
             AND tablename = 'supplier_offers'
             AND policyname = 'supplier_offers_company_access'
       ) THEN
        EXECUTE $policy$
            CREATE POLICY supplier_offers_company_access ON supplier_offers
                FOR ALL USING (company_id = (auth.jwt() ->> 'company_id')::uuid)
                WITH CHECK (company_id = (auth.jwt() ->> 'company_id')::uuid)
        $policy$;
    END IF;
END
$$;

DO $outer$
BEGIN
    IF to_regprocedure('public.update_updated_at()') IS NULL THEN
        EXECUTE $create_function$
            CREATE FUNCTION public.update_updated_at()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $function$
            BEGIN
                NEW.updated_at = now();
                RETURN NEW;
            END
            $function$
        $create_function$;
    END IF;
END
$outer$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgrelid = 'public.product_search_items'::regclass
          AND tgname = 'set_product_search_items_updated_at'
          AND NOT tgisinternal
    ) THEN
        EXECUTE $trigger$
            CREATE TRIGGER set_product_search_items_updated_at
                BEFORE UPDATE ON product_search_items
                FOR EACH ROW EXECUTE FUNCTION update_updated_at()
        $trigger$;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgrelid = 'public.sourcing_plans'::regclass
          AND tgname = 'set_sourcing_plans_updated_at'
          AND NOT tgisinternal
    ) THEN
        EXECUTE $trigger$
            CREATE TRIGGER set_sourcing_plans_updated_at
                BEFORE UPDATE ON sourcing_plans
                FOR EACH ROW EXECUTE FUNCTION update_updated_at()
        $trigger$;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgrelid = 'public.supplier_offers'::regclass
          AND tgname = 'set_supplier_offers_updated_at'
          AND NOT tgisinternal
    ) THEN
        EXECUTE $trigger$
            CREATE TRIGGER set_supplier_offers_updated_at
                BEFORE UPDATE ON supplier_offers
                FOR EACH ROW EXECUTE FUNCTION update_updated_at()
        $trigger$;
    END IF;
END
$$;
