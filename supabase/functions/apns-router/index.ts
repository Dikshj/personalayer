import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  Deno.env.get('SUPABASE_URL')!,
  Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
)

Deno.serve(async (req) => {
  if (req.method !== 'POST') {
    return new Response('Method not allowed', { status: 405 })
  }

  const { user_id, route_type, metadata } = await req.json()
  if (!user_id || !route_type) {
    return new Response(JSON.stringify({ error: 'missing user_id or route_type' }), { status: 400 })
  }

  // Fetch device tokens for user (apns_token per 001 schema)
  const { data: tokens, error } = await supabase
    .from('push_tokens')
    .select('apns_token, platform')
    .eq('user_id', user_id)
    .eq('is_active', true)

  if (error || !tokens || tokens.length === 0) {
    return new Response(JSON.stringify({ queued: 0, sent: 0 }), { status: 200 })
  }

  // APNs payload — routing metadata ONLY, no insight text
  const payload = {
    aps: {
      'content-available': 1,
      sound: 'default'
    },
    pl_route_type: route_type,
    pl_metadata: metadata || {},
    pl_timestamp: Date.now()
  }

  // In production, POST to api.push.apple.com:443/3/device/{apns_token}
  // using JWT signed with APNs auth key. For now, log and count.
  for (const t of tokens) {
    console.log(`APNs [${t.platform}] ${t.apns_token.substring(0, 8)}... payload:`, JSON.stringify(payload))
  }

  return new Response(JSON.stringify({
    queued: tokens.length,
    sent: 0,
    payload_summary: { route_type, metadata_keys: Object.keys(metadata || {}) }
  }), { status: 200 })
})
