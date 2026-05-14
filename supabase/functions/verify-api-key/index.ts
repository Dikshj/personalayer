import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  Deno.env.get('SUPABASE_URL')!,
  Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
)

Deno.serve(async (req) => {
  if (req.method !== 'POST') {
    return new Response('Method not allowed', { status: 405 })
  }

  const { api_key } = await req.json()
  if (!api_key) {
    return new Response(JSON.stringify({ valid: false, error: 'missing api_key' }), { status: 400 })
  }

  const { data, error } = await supabase.rpc('verify_api_key', { key_text: api_key })
  if (error || !data || data.length === 0 || !data[0].valid) {
    return new Response(JSON.stringify({ valid: false }), { status: 401 })
  }

  const row = data[0]

  // Touch last_used_at asynchronously (fire and forget)
  supabase.rpc('touch_api_key', { key_id: row.key_id }).then(() => {}).catch(() => {})

  return new Response(JSON.stringify({
    valid: true,
    developer_id: row.developer_id,
    app_id: row.app_id,
    env: row.env
  }), { status: 200 })
})
