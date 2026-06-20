// Personal Layer Extension Background Service Worker (MV3)
// Bridges website postMessage calls to the local Python runtime.

const DAEMON_URL = 'http://127.0.0.1:7823';
const HEALTH_INTERVAL_MS = 30000;

let lastHealthCheck = 0;
let daemonAvailable = false;

// Message routing: from popup/content -> background -> local runtime.
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  switch (request.type) {
    case 'CL_GET_BUNDLE':
      handleGetBundle(request.origin).then(sendResponse).catch(err => sendResponse({ error: err.message }));
      return true;
    case 'CL_TRACK':
      handleTrack(request.data, request.origin).then(sendResponse).catch(err => sendResponse({ error: err.message }));
      return true;
    case 'CL_CHECK_AVAILABLE':
      checkDaemon().then(sendResponse).catch(() => sendResponse({ available: false }));
      return true;
    case 'CL_REQUEST_APPROVAL':
      handleApprovalRequest(request.domain).then(sendResponse).catch(err => sendResponse({ error: err.message }));
      return true;
    case 'PL_FEED_EVENT':
      handleFeedEvent(request.payload).then(sendResponse).catch(err => sendResponse({ error: err.message }));
      return true;
    // New: SDK bridge messages via window.postMessage
    case 'GET_BUNDLE':
      handleGetBundle(request.origin || sender.origin).then(r => sendResponse({ success: true, data: r }))
        .catch(e => sendResponse({ success: false, error: e.message }));
      return true;
    case 'TRACK':
      handleTrack(request.payload, request.origin || sender.origin).then(r => sendResponse({ success: true, data: r }))
        .catch(e => sendResponse({ success: false, error: e.message }));
      return true;
  }
});

/** Check local runtime availability. */
async function checkDaemon(force = false) {
  const now = Date.now();
  if (!force && now - lastHealthCheck < HEALTH_INTERVAL_MS) {
    return { available: daemonAvailable };
  }

  try {
    const res = await fetch(`${DAEMON_URL}/health`, { method: 'GET', mode: 'cors' });
    daemonAvailable = res.ok;
    lastHealthCheck = now;
    return { available: res.ok };
  } catch {
    daemonAvailable = false;
    lastHealthCheck = now;
    return { available: false };
  }
}

async function handleGetBundle(origin) {
  const health = await checkDaemon(true);
  if (!health.available) throw new Error('Personal Layer local runtime not available');

  const res = await fetch(`${DAEMON_URL}/v1/context/bundle`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Origin': origin },
    body: JSON.stringify({
      user_id: 'local_user',
      app_id: 'browser_extension',
      intent: 'extension_context_bridge',
      requested_scopes: ['profile_summary', 'preferences', 'feature_signals']
    })
  });
  if (res.status === 403) throw new Error('Domain not approved. Grant permission in Personal Layer.');
  if (!res.ok) throw new Error(`Bundle fetch failed: ${res.status}`);
  return await res.json();
}

async function handleTrack(data, origin) {
  const health = await checkDaemon(true);
  if (!health.available) throw new Error('Personal Layer local runtime not available');

  const res = await fetch(`${DAEMON_URL}/v1/ingest/extension`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Origin': origin
    },
    body: JSON.stringify(data)
  });
  if (res.status === 403) throw new Error('Domain not approved');
  if (!res.ok) throw new Error(`Track failed: ${res.status}`);
  return await res.json();
}

async function handleFeedEvent(payload) {
  const health = await checkDaemon(true);
  if (!health.available) throw new Error('Personal Layer local runtime not available');

  const res = await fetch(`${DAEMON_URL}/feed-event`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error(`Feed event failed: ${res.status}`);
  return await res.json();
}

async function handleApprovalRequest(domain) {
  try {
    const res = await fetch(`${DAEMON_URL}/v1/ingest/extension`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event_type: 'approval_request', domain })
    });
    return { requested: res.ok };
  } catch {
    return { requested: false };
  }
}

// Periodic background health check
setInterval(async () => {
  const result = await checkDaemon();
  chrome.storage.local.set({
    daemonAvailable: result.available,
    lastCheck: Date.now()
  });
}, HEALTH_INTERVAL_MS);

// Initial check
chrome.runtime.onStartup.addListener(() => checkDaemon(true));
checkDaemon(true);
