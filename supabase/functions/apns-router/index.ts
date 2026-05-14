import { createClient } from '@supabase/supabase-js'
import { encodeBase64 } from 'https://deno.land/std@0.224.0/encoding/base64.ts'

const supabase = createClient(
  Deno.env.get('SUPABASE_URL')!,
  Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
)

interface APNsPayload {
  aps: {
    'content-available': number
    sound?: string
  }
  pl_route_type: string
  pl_metadata: Record<string, unknown>
  pl_timestamp: number
}

async function generateAPNsJWT(): Promise<string> {
  const keyId = Deno.env.get('APNS_KEY_ID')!
  const teamId = Deno.env.get('APNS_TEAM_ID')!
  const privateKey = Deno.env.get('APNS_PRIVATE_KEY')!

  const header = { alg: 'ES256', kid: keyId }
  const now = Math.floor(Date.now() / 1000)
  const claims = { iss: teamId, iat: now }

  const encoder = new TextEncoder()
  const headerB64 = btoa(JSON.stringify(header)).replace(/=/g, '')
  const claimsB64 = btoa(JSON.stringify(claims)).replace(/=/g, '')
  const signingInput = `${headerB64}.${claimsB64}`

  // Import private key and sign
  const pkcs8 = privateKey.replace(/-----BEGIN EC PRIVATE KEY-----/, '')
    .replace(/-----END EC PRIVATE KEY-----/, '')
    .replace(/\s/g, '')
  const keyData = Uint8Array.from(atob(pkcs8), c => c.charCodeAt(0))

  const cryptoKey = await crypto.subtle.importKey(
    'pkcs8',
    keyData.buffer,
    { name: 'ECDSA', namedCurve: 'P-256' },
    false,
    ['sign']
  )

  const signature = await crypto.subtle.sign(
    { name: 'ECDSA', hash: 'SHA-256' },
    cryptoKey,
    encoder.encode(signingInput)
  )

  const sigB64 = encodeBase64(new Uint8Array(signature)).replace(/=/g, '')
  return `${headerB64}.${claimsB64}.${sigB64}`
}

async function sendAPNs(token: string, payload: APNsPayload, jwt: string, isProduction: boolean): Promise<{ success: boolean; status?: number }> {
  const host = isProduction ? 'api.push.apple.com' : 'api.sandbox.push.apple.com'
  const url = `https://${host}/3/device/${token}`

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Authorization': `bearer ${jwt}`,
      'Content-Type': 'application/json',
      'apns-topic': 'com.personalayer.ios',
      'apns-push-type': 'background',
      'apns-priority': '5'
    },
    body: JSON.stringify(payload)
  })

  return { success: response.status === 200, status: response.status }
}

Deno.serve(async (req) => {
  if (req.method !== 'POST') {
    return new Response('Method not allowed', { status: 405 })
  }

  const { user_id, route_type, metadata } = await req.json()
  if (!user_id || !route_type) {
    return new Response(JSON.stringify({ error: 'missing user_id or route_type' }), { status: 400 })
  }

  const { data: tokens, error } = await supabase
    .from('push_tokens')
    .select('apns_token, platform, environment')
    .eq('user_id', user_id)
    .eq('is_active', true)

  if (error || !tokens || tokens.length === 0) {
    return new Response(JSON.stringify({ queued: 0, sent: 0 }), { status: 200 })
  }

  const payload: APNsPayload = {
    aps: { 'content-available': 1 },
    pl_route_type: route_type,
    pl_metadata: metadata || {},
    pl_timestamp: Date.now()
  }

  let jwt: string | null = null
  let sent = 0
  let failed = 0

  for (const t of tokens) {
    try {
      if (!jwt) jwt = await generateAPNsJWT()
      const isProduction = t.environment === 'production'
      const result = await sendAPNs(t.apns_token, payload, jwt, isProduction)
      if (result.success) {
        sent++
      } else if (result.status === 410) {
        // Token invalid — deactivate
        await supabase.from('push_tokens')
          .update({ is_active: false })
          .eq('apns_token', t.apns_token)
        failed++
      } else {
        failed++
      }
    } catch (e) {
      console.error(`APNs send failed for token ${t.apns_token.substring(0, 8)}:`, e)
      failed++
    }
  }

  return new Response(JSON.stringify({
    queued: tokens.length,
    sent,
    failed,
    payload_summary: { route_type, metadata_keys: Object.keys(metadata || {}) }
  }), { status: 200 })
})
