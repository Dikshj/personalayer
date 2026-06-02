
import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

serve(async (req) => {
  const { userId, message, badge = 1, sound = 'default' } = await req.json().catch(() => ({}))
  if (!userId || !message) {
    return new Response(JSON.stringify({ sent: false, error: 'missing_params' }), { status: 400 })
  }

  const supabase = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
  )

  const { data: tokens, error } = await supabase
    .from('push_tokens')
    .select('apns_token, environment')
    .eq('user_id', userId)
    .eq('is_active', true)

  if (error) {
    return new Response(JSON.stringify({ sent: false, error: error.message }), { status: 500 })
  }

  const apnsKey = Deno.env.get('APNS_AUTH_KEY')!
  const apnsKeyId = Deno.env.get('APNS_KEY_ID')!
  const apnsTeamId = Deno.env.get('APNS_TEAM_ID')!
  const bundleId = Deno.env.get('APNS_BUNDLE_ID')!

  const results = []
  for (const token of tokens || []) {
    const endpoint = token.environment === 'production'
      ? 'https://api.push.apple.com'
      : 'https://api.sandbox.push.apple.com'

    const res = await fetch(`${endpoint}/3/device/${token.apns_token}`, {
      method: 'POST',
      headers: {
        'authorization': `bearer ${apnsKey}`,
        'apns-topic': bundleId,
        'apns-push-type': 'alert',
        'content-type': 'application/json',
      },
      body: JSON.stringify({ aps: { alert: message, badge, sound } }),
    })
    results.push({ token: token.apns_token.slice(0, 8) + '...', status: res.status })
  }

  return new Response(JSON.stringify({ sent: true, count: results.length, results }), { status: 200 })
})
