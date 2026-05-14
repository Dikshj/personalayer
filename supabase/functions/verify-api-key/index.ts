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
  if (!api_key || typeof api_key !== 'string') {
    return new Response(JSON.stringify({ error: 'missing api_key' }), { status: 400 })
  }

  // Call the RPC that matches the actual schema
  const { data, error } = await supabase.rpc('verify_api_key', {
    api_key: api_key
  })

  if (error) {
    return new Response(JSON.stringify({ error: error.message }), { status: 500 })
  }

  if (!data || data.length === 0) {
    return new Response(JSON.stringify({ valid: false }), { status: 200 })
  }

  const key = data[0]

  // Touch last_used_at asynchronously (fire-and-forget)
  supabase.rpc('touch_api_key', { key_id: key.key_id }).catch(() => {})

  return new Response(JSON.stringify({
    valid: key.valid === true,
    key_id: key.key_id,
    developer_id: key.developer_id,
    app_id: key.app_id,
    env: key.env
  }), { status: 200 })
})
