import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  Deno.env.get('SUPABASE_URL')!,
  Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
)

interface APNsPayload {
  aps: {
    'content-available': number;
    alert?: never;
    sound?: never;
    badge?: never;
  };
  route: {
    type: string;
    route_id: string;
    user_id: string;
    device_id: string;
  };
}

/** Parse APNs .p8 PEM private key into raw base64. */
function parsePEMKey(pem: string): Uint8Array {
  const lines = pem.split('\n').map(l => l.trim()).filter(l => l.length > 0)
  // Remove PEM headers/footers if present
  const bodyLines = lines.filter(l => !l.startsWith('-----'))
  const base64 = bodyLines.join('')
  return Uint8Array.from(atob(base64), c => c.charCodeAt(0))
}

/** Sign ES256 JWT using Web Crypto API. */
async function signAPNsJWT(keyId: string, teamId: string, privateKeyPEM: string): Promise<string> {
  const encoder = new TextEncoder()
  const header = { alg: 'ES256', kid: keyId }
  const claims = { iss: teamId, iat: Math.floor(Date.now() / 1000) }

  const headerB64 = btoa(JSON.stringify(header)).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
  const claimsB64 = btoa(JSON.stringify(claims)).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
  const signingInput = `${headerB64}.${claimsB64}`

  const keyData = parsePEMKey(privateKeyPEM)

  const cryptoKey = await crypto.subtle.importKey(
    'pkcs8',
    keyData,
    { name: 'ECDSA', namedCurve: 'P-256' },
    false,
    ['sign']
  )

  const signature = await crypto.subtle.sign(
    { name: 'ECDSA', hash: 'SHA-256' },
    cryptoKey,
    encoder.encode(signingInput)
  )

  const sigB64 = btoa(String.fromCharCode(...new Uint8Array(signature)))
    .replace(/=/g, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_')

  return `${signingInput}.${sigB64}`
}

/** Send a single APNs notification via HTTP/2. */
async function sendAPNs(
  apnsHost: string,
  jwt: string,
  bundleId: string,
  token: string,
  payload: APNsPayload
): Promise<{ ok: boolean; status: number; body: string }> {
  const response = await fetch(`https://${apnsHost}/3/device/${token}`, {
    method: 'POST',
    headers: {
      'authorization': `bearer ${jwt}`,
      'apns-topic': bundleId,
      'apns-push-type': 'background',
      'apns-priority': '5',
      'content-type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
  const body = await response.text().catch(() => '')
  return { ok: response.ok, status: response.status, body }
}

Deno.serve(async (req) => {
  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'Method not allowed' }), { status: 405 })
  }

  const { data: routes, error } = await supabase
    .from('notification_routes')
    .select(`
      id,
      user_id,
      device_id,
      push_token_id,
      notification_type,
      payload_kind,
      push_tokens:push_token_id (apns_token, platform)
    `)
    .eq('status', 'queued')
    .lt('deliver_after', new Date().toISOString())
    .limit(100)

  if (error) {
    return new Response(JSON.stringify({ error: error.message }), { status: 500 })
  }

  if (!routes || routes.length === 0) {
    return new Response(JSON.stringify({ queued: 0, sent: 0, failed: 0 }), { status: 200 })
  }

  const keyId = Deno.env.get('APNS_KEY_ID')
  const teamId = Deno.env.get('APNS_TEAM_ID')
  const bundleId = Deno.env.get('APNS_BUNDLE_ID')
  const privateKeyPEM = Deno.env.get('APNS_PRIVATE_KEY')

  if (!keyId || !teamId || !privateKeyPEM || !bundleId) {
    return new Response(JSON.stringify({ error: 'APNs credentials not configured' }), { status: 500 })
  }

  // Generate JWT (valid for ~1 hour, but we regenerate per batch)
  let jwt: string
  try {
    jwt = await signAPNsJWT(keyId, teamId, privateKeyPEM)
  } catch (e: any) {
    return new Response(JSON.stringify({ error: `JWT signing failed: ${e.message}` }), { status: 500 })
  }

  const isProduction = Deno.env.get('APNS_ENV') !== 'sandbox'
  const apnsHost = isProduction ? 'api.push.apple.com' : 'api.sandbox.push.apple.com'

  let sent = 0
  let failed = 0
  const results: Array<{ route_id: string; status: string; error?: string }> = []

  for (const route of routes) {
    const pushToken = route.push_tokens?.apns_token
    if (!pushToken) {
      failed++
      results.push({ route_id: route.id, status: 'failed', error: 'missing_apns_token' })
      continue
    }

    const payload: APNsPayload = {
      aps: { 'content-available': 1 },
      route: {
        type: route.notification_type,
        route_id: route.id,
        user_id: route.user_id,
        device_id: route.device_id
      }
    }

    try {
      const res = await sendAPNs(apnsHost, jwt, bundleId, pushToken, payload)

      if (res.status === 410) {
        // Token invalid - deactivate
        await supabase.from('push_tokens').update({ is_active: false }).eq('id', route.push_token_id)
        failed++
        results.push({ route_id: route.id, status: 'failed', error: `invalid_token_410: ${res.body}` })
      } else if (res.ok) {
        sent++
        results.push({ route_id: route.id, status: 'sent' })
      } else if (res.status === 429) {
        // Rate limited - mark as queued to retry
        const retryAfter = parseInt(res.body.match(/\d+/)?.[0] ?? '60', 10)
        const nextAttempt = new Date(Date.now() + retryAfter * 1000).toISOString()
        await supabase.from('notification_routes')
          .update({ status: 'queued', deliver_after: nextAttempt })
          .eq('id', route.id)
        failed++
        results.push({ route_id: route.id, status: 'failed', error: `rate_limited_429: retry_after=${retryAfter}` })
      } else {
        failed++
        results.push({ route_id: route.id, status: 'failed', error: `http_${res.status}: ${res.body}` })
      }
    } catch (e: any) {
      failed++
      results.push({ route_id: route.id, status: 'failed', error: `network: ${e.message}` })
    }
  }

  // Batch update statuses
  const sentRoutes = results.filter(r => r.status === 'sent')
  const failedRoutes = results.filter(r => r.status === 'failed')

  if (sentRoutes.length > 0) {
    await supabase.from('notification_routes')
      .update({ status: 'sent', sent_at: new Date().toISOString() })
      .in('id', sentRoutes.map(r => r.route_id))
  }
  if (failedRoutes.length > 0) {
    await supabase.from('notification_routes')
      .update({ status: 'failed', error_detail: failedRoutes[0].error })
      .in('id', failedRoutes.map(r => r.route_id))
  }

  return new Response(JSON.stringify({
    queued: routes.length,
    sent,
    failed,
    payload_summary: 'routing_metadata_only',
    results
  }), { status: 200 })
})
