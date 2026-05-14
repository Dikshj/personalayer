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

// Base64url to Base64 helper for JWT
function base64urlToBase64(str: string): string {
  let base64 = str.replace(/-/g, '+').replace(/_/g, '/');
  const pad = base64.length % 4;
  if (pad) base64 += '='.repeat(4 - pad);
  return base64;
}

// Simple ES256 JWT signing using Web Crypto API
async function signJWT(header: object, claims: object, privateKeyPEM: string): Promise<string> {
  const encoder = new TextEncoder();
  const headerB64 = btoa(JSON.stringify(header)).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');
  const claimsB64 = btoa(JSON.stringify(claims)).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');
  const signingInput = `${headerB64}.${claimsB64}`;

  // Parse PEM private key
  const cleanedKey = privateKeyPEM
    .replace(/-----BEGIN EC PRIVATE KEY-----/g, '')
    .replace(/-----END EC PRIVATE KEY-----/g, '')
    .replace(/-----BEGIN PRIVATE KEY-----/g, '')
    .replace(/-----END PRIVATE KEY-----/g, '')
    .replace(/\s/g, '')
    .trim();

  const keyData = Uint8Array.from(atob(base64urlToBase64(cleanedKey)), c => c.charCodeAt(0));

  const cryptoKey = await crypto.subtle.importKey(
    'pkcs8',
    keyData,
    { name: 'ECDSA', namedCurve: 'P-256' },
    false,
    ['sign']
  );

  const signature = await crypto.subtle.sign(
    { name: 'ECDSA', hash: 'SHA-256' },
    cryptoKey,
    encoder.encode(signingInput)
  );

  const sigB64 = btoa(String.fromCharCode(...new Uint8Array(signature)))
    .replace(/=/g, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_');

  return `${signingInput}.${sigB64}`;
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

  // Generate JWT
  const now = Math.floor(Date.now() / 1000)
  let jwt: string
  try {
    jwt = await signJWT(
      { alg: 'ES256', kid: keyId },
      { iss: teamId, iat: now },
      privateKeyPEM
    )
  } catch (e) {
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
      const response = await fetch(`https://${apnsHost}/3/device/${pushToken}`, {
        method: 'POST',
        headers: {
          'authorization': `bearer ${jwt}`,
          'apns-topic': bundleId,
          'apns-push-type': 'background',
          'apns-priority': '5',
          'content-type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (response.status === 410) {
        // Token is invalid, deactivate it
        await supabase.from('push_tokens').update({ is_active: false }).eq('id', route.push_token_id)
        failed++
        results.push({ route_id: route.id, status: 'failed', error: 'invalid_token_410' })
      } else if (response.ok) {
        sent++
        results.push({ route_id: route.id, status: 'sent' })
      } else {
        const errorBody = await response.text().catch(() => 'unknown')
        failed++
        results.push({ route_id: route.id, status: 'failed', error: `http_${response.status}: ${errorBody}` })
      }
    } catch (e) {
      failed++
      results.push({ route_id: route.id, status: 'failed', error: `network: ${e.message}` })
    }
  }

  // Batch update statuses
  for (const r of results.filter(r => r.status === 'sent')) {
    await supabase.from('notification_routes')
      .update({ status: 'sent', sent_at: new Date().toISOString() })
      .eq('id', r.route_id);
  }
  for (const r of results.filter(r => r.status === 'failed')) {
    await supabase.from('notification_routes')
      .update({ status: 'failed', error_detail: r.error })
      .eq('id', r.route_id);
  }

  return new Response(JSON.stringify({
    queued: routes.length,
    sent,
    failed,
    payload_summary: 'routing_metadata_only',
    results
  }), { status: 200 })
})
