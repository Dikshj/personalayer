
import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

serve(async (req) => {
  const { apiKey, appId } = await req.json().catch(() => ({}))
  if (!apiKey || !appId) {
    return new Response(JSON.stringify({ valid: false, error: 'missing_params' }), { status: 400 })
  }

  const supabase = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
  )

  const { data, error } = await supabase
    .from('developer_apps')
    .select('id, app_id, name, scopes, status')
    .eq('app_id', appId)
    .single()

  if (error || !data) {
    return new Response(JSON.stringify({ valid: false, error: 'app_not_found' }), { status: 404 })
  }

  // In production, verify API key against a secrets table or HMAC here.
  // For thin-cloud mode, we only validate the app exists and is active.
  if (data.status !== 'active') {
    return new Response(JSON.stringify({ valid: false, error: 'app_not_active' }), { status: 403 })
  }

  return new Response(JSON.stringify({ valid: true, app: data }), { status: 200 })
})
