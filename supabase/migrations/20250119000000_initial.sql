
-- Personal Layer Supabase Thin Cloud Schema
-- NO raw events, embeddings, graph nodes, bundles, or feature signals are stored here.

-- 1. Developer registry (for app onboarding + API key verification)
CREATE TABLE IF NOT EXISTS public.developer_apps (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    app_id text UNIQUE NOT NULL,
    name text NOT NULL,
    developer_id uuid REFERENCES auth.users(id),
    redirect_uris text[] DEFAULT '{}',
    scopes text[] DEFAULT '{}',
    status text DEFAULT 'pending',
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- 2. App consent metadata (thin: user_id + app_id + scopes + status only)
CREATE TABLE IF NOT EXISTS public.user_consent (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
    app_id text NOT NULL REFERENCES public.developer_apps(app_id) ON DELETE CASCADE,
    scopes text[] DEFAULT '{}',
    status text DEFAULT 'granted',
    revoked_at timestamptz,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    UNIQUE(user_id, app_id)
);

-- 3. Push token routing table (for APNs)
CREATE TABLE IF NOT EXISTS public.push_tokens (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
    device_id text NOT NULL,
    apns_token text NOT NULL,
    platform text NOT NULL DEFAULT 'ios',
    environment text NOT NULL DEFAULT 'sandbox',
    is_active boolean DEFAULT true,
    revoked_at timestamptz,
    created_at timestamptz DEFAULT now(),
    UNIQUE(user_id, device_id)
);

-- 4. Audit metadata (only app access logs, no behavioral data)
CREATE TABLE IF NOT EXISTS public.access_audit (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
    app_id text NOT NULL,
    action text NOT NULL,
    status text NOT NULL,
    ip_hash text,
    created_at timestamptz DEFAULT now()
);

-- RLS: Users can only see their own data
ALTER TABLE public.developer_apps ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_consent ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.push_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.access_audit ENABLE ROW LEVEL SECURITY;

CREATE POLICY dev_apps_select ON public.developer_apps
    FOR SELECT USING (developer_id = auth.uid());

CREATE POLICY consent_select ON public.user_consent
    FOR SELECT USING (user_id = auth.uid());
CREATE POLICY consent_insert ON public.user_consent
    FOR INSERT WITH CHECK (user_id = auth.uid());
CREATE POLICY consent_update ON public.user_consent
    FOR UPDATE USING (user_id = auth.uid());

CREATE POLICY push_select ON public.push_tokens
    FOR SELECT USING (user_id = auth.uid());
CREATE POLICY push_insert ON public.push_tokens
    FOR INSERT WITH CHECK (user_id = auth.uid());
CREATE POLICY push_update ON public.push_tokens
    FOR UPDATE USING (user_id = auth.uid());

CREATE POLICY audit_select ON public.access_audit
    FOR SELECT USING (user_id = auth.uid());

-- Function for observability edge function
CREATE OR REPLACE FUNCTION public.log_access_audit(
    p_user_id uuid,
    p_app_id text,
    p_action text,
    p_status text,
    p_ip_hash text DEFAULT NULL
) RETURNS void AS $$
BEGIN
    INSERT INTO public.access_audit (user_id, app_id, action, status, ip_hash)
    VALUES (p_user_id, p_app_id, p_action, p_status, p_ip_hash);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
