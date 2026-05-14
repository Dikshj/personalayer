// Personal Layer Extension Background Service Worker (MV3)
// Primary: Native Messaging to macOS daemon
// Fallback: Direct localhost HTTP

const DAEMON_URL = 'http://127.0.0.1:7432';
const HEALTH_INTERVAL_MS = 30000;
const NATIVE_HOST_NAME = 'com.personalayer.nativemessaging';

let lastHealthCheck = 0;
let daemonAvailable = false;
let nativeMessagingAvailable = false;

// Message routing: from popup/content -> background -> native host or localhost
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  switch (request.type) {
    case 'CL_GET_BUNDLE':
      handleGetBundle(request.origin).then(sendResponse).catch(err => sendResponse({ error: err.message }));
      return true;
    case 'CL_TRACK':
      handleTrack(request.data, request.origin).then(sendResponse).catch(err => sendResponse({ error: err.message }));
      return true;
    case 'CL_CHECK_AVAILABLE':
      checkDaemon().then(sendResponse).catch(() => sendResponse({ available: false, nativeMessaging: false }));
      return true;
    case 'CL_REQUEST_APPROVAL':
      handleApprovalRequest(request.domain).then(sendResponse).catch(err => sendResponse({ error: err.message }));
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

/** Check daemon via native messaging first, then localhost fallback. */
async function checkDaemon(force = false) {
  const now = Date.now();
  if (!force && now - lastHealthCheck < HEALTH_INTERVAL_MS) {
    return { available: daemonAvailable, nativeMessaging: nativeMessagingAvailable };
  }

  // Try native messaging first
  try {
    const nmResult = await sendNativeMessage({ action: 'health' });
    daemonAvailable = nmResult.ok === true;
    nativeMessagingAvailable = true;
    lastHealthCheck = now;
    return { available: daemonAvailable, nativeMessaging: true };
  } catch {
    nativeMessagingAvailable = false;
  }

  // Fallback to localhost
  try {
    const res = await fetch(`${DAEMON_URL}/health`, { method: 'GET', mode: 'cors' });
    daemonAvailable = res.ok;
    lastHealthCheck = now;
    return { available: res.ok, nativeMessaging: false };
  } catch {
    daemonAvailable = false;
    lastHealthCheck = now;
    return { available: false, nativeMessaging: false };
  }
}

/** Send message to native messaging host. */
function sendNativeMessage(message) {
  return new Promise((resolve, reject) => {
    const port = chrome.runtime.connectNative(NATIVE_HOST_NAME);
    let responded = false;
    port.onMessage.addListener((response) => {
      responded = true;
      resolve(response);
      port.disconnect();
    });
    port.onDisconnect.addListener(() => {
      if (!responded) {
        reject(new Error('Native messaging disconnected'));
      }
    });
    port.postMessage(message);
    setTimeout(() => {
      if (!responded) {
        reject(new Error('Native messaging timeout'));
        port.disconnect();
      }
    }, 5000);
  });
}

async function handleGetBundle(origin) {
  // Try native messaging first
  if (nativeMessagingAvailable) {
    try {
      return await sendNativeMessage({ action: 'get_bundle', origin });
    } catch {
      // Fall through to localhost
    }
  }

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
  if (nativeMessagingAvailable) {
    try {
      return await sendNativeMessage({ action: 'track', payload: data, origin });
    } catch {
      // Fall through
    }
  }

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
    nativeMessagingAvailable: result.nativeMessaging,
    lastCheck: Date.now()
  });
}, HEALTH_INTERVAL_MS);

// Initial check
chrome.runtime.onStartup.addListener(() => checkDaemon(true));
checkDaemon(true);
