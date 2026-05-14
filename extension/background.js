// Personal Layer Extension Background Service Worker (MV3)

const DAEMON_URL = 'http://127.0.0.1:7432';
const HEALTH_INTERVAL_MS = 30000;

let lastHealthCheck = 0;
let daemonAvailable = false;

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === 'CL_GET_BUNDLE') {
    handleGetBundle(request.origin).then(sendResponse).catch(err => sendResponse({ error: err.message }));
    return true;
  }
  if (request.type === 'CL_TRACK') {
    handleTrack(request.data, request.origin).then(sendResponse).catch(err => sendResponse({ error: err.message }));
    return true;
  }
  if (request.type === 'CL_CHECK_AVAILABLE') {
    checkDaemon().then(sendResponse).catch(() => sendResponse({ available: false }));
    return true;
  }
  if (request.type === 'CL_REQUEST_APPROVAL') {
    handleApprovalRequest(request.domain).then(sendResponse).catch(err => sendResponse({ error: err.message }));
    return true;
  }
});

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
  if (!health.available) throw new Error('Personal Layer daemon not available');

  const res = await fetch(`${DAEMON_URL}/v1/context/bundle`, {
    headers: { 'Origin': origin }
  });
  if (res.status === 403) throw new Error('Domain not approved. Grant permission in Personal Layer menu bar.');
  if (!res.ok) throw new Error(`Bundle fetch failed: ${res.status}`);
  return await res.json();
}

async function handleTrack(data, origin) {
  const health = await checkDaemon(true);
  if (!health.available) throw new Error('Personal Layer daemon not available');

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

async function handleApprovalRequest(domain) {
  // Native messaging request to ask daemon for approval
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
  chrome.storage.local.set({ daemonAvailable: result.available, lastCheck: Date.now() });
}, HEALTH_INTERVAL_MS);

// Initial check
chrome.runtime.onStartup.addListener(() => checkDaemon(true));
checkDaemon(true);
