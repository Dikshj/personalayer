
import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

serve(async (req) => {
  const { userId, appId, action, status } = await req.json().catch(() => ({}))
  if (!userId || !appId || !action) {
    return new Response(JSON.stringify({ logged: false, error: 'missing_params' }), { status: 400 })
  }

  const supabase = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
  )

  const { error } = await supabase.rpc('log_access_audit', {
    p_user_id: userId,
    p_app_id: appId,
    p_action: action,
    p_status: status || 'ok',
    p_ip_hash: req.headers.get('x-forwarded-for')?.split(',')[0]?.trim() || null,
  })

  if (error) {
    return new Response(JSON.stringify({ logged: false, error: error.message }), { status: 500 })
  }

  return new Response(JSON.stringify({ logged: true }), { status: 200 })
})
