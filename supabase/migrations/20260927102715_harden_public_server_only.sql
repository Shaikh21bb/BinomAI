-- BINOM AI reads and writes business tables only through FastAPI.
-- Keep the public schema unavailable to browser Data API roles while retaining
-- access for the direct database connection and Supabase service_role.

ALTER TABLE IF EXISTS public.companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.invites ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.plan_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.generated_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.product_search_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.tender_lots ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.analysis_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.supplier_offers ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.sourcing_settings ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES ON TABLE
    public.companies,
    public.users,
    public.projects,
    public.invites,
    public.plan_requests,
    public.documents,
    public.chat_sessions,
    public.chat_messages,
    public.generated_documents,
    public.product_search_items,
    public.tender_lots,
    public.notifications,
    public.analysis_results,
    public.supplier_offers,
    public.sourcing_settings
FROM anon, authenticated;

-- Cover the remaining foreign keys reported by the database advisor.
CREATE INDEX IF NOT EXISTS idx_documents_uploaded_by ON public.documents(uploaded_by);
CREATE INDEX IF NOT EXISTS idx_invites_created_by ON public.invites(created_by);
CREATE INDEX IF NOT EXISTS idx_projects_created_by ON public.projects(created_by);
