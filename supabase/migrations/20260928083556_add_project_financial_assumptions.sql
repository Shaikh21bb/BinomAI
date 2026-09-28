-- Persist project-level costs that are not part of supplier quotes and a
-- configurable risk reserve. Existing sourcing plans receive an explicit 5%
-- contingency default that users can adjust or set to zero.
ALTER TABLE public.sourcing_plans
    ADD COLUMN IF NOT EXISTS other_costs_kzt numeric(18,2) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS contingency_pct numeric(5,2) NOT NULL DEFAULT 5;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_sourcing_plans_other_costs'
          AND conrelid = 'public.sourcing_plans'::regclass
    ) THEN
        ALTER TABLE public.sourcing_plans
            ADD CONSTRAINT ck_sourcing_plans_other_costs
            CHECK (other_costs_kzt >= 0);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_sourcing_plans_contingency'
          AND conrelid = 'public.sourcing_plans'::regclass
    ) THEN
        ALTER TABLE public.sourcing_plans
            ADD CONSTRAINT ck_sourcing_plans_contingency
            CHECK (contingency_pct >= 0 AND contingency_pct <= 100);
    END IF;
END
$$;
