import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  Deno.env.get('SUPABASE_URL')!,
  Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
)

Deno.serve(async (req) => {
  if (req.method !== 'POST') {
    return new Response('Method not allowed', { status: 405 })
  }

  const { event_type, app_id, metadata } = await req.json()

  // Only log cloud metadata — no raw events, no insight text, no PII
  const log = {
    event_type,
    app_id,
    metadata_keys: Object.keys(metadata || {}),
    timestamp: new Date().toISOString()
  }

  console.log(JSON.stringify(log))

  return new Response(JSON.stringify({ logged: true }), { status: 200 })
})
