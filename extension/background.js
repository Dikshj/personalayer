// extension/background.js
const API_BASE = "http://localhost:7823";
const ENDPOINT = `${API_BASE}/event`;
const CONTEXT_EVENT_ENDPOINT = `${API_BASE}/v1/ingest/extension`;
const CONTEXT_BUNDLE_ENDPOINT = `${API_BASE}/v1/context/bundle`;
const CONTEXT_HEARTBEAT_ENDPOINT = `${API_BASE}/v1/context/heartbeat`;

// tabData[tabId] = { url, title, startTime }
const tabData = {};

// When user switches to a tab, record start time
chrome.tabs.onActivated.addListener(({ tabId, previousTabId }) => {
  if (previousTabId !== undefined) {
    flushTab(previousTabId);
  }
  chrome.tabs.get(tabId, (tab) => {
    if (chrome.runtime.lastError || !tab) return;
    tabData[tabId] = {
      url: tab.url || "",
      title: tab.title || "",
      startTime: Date.now(),
    };
  });
});

// When a page finishes loading in a tab, reset its timer
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status !== "complete") return;
  if (!tab.url || isSkipped(tab.url)) return;
  tabData[tabId] = {
    url: tab.url,
    title: tab.title || "",
    startTime: Date.now(),
  };
});

// When a tab closes, flush it
chrome.tabs.onRemoved.addListener((tabId) => {
  flushTab(tabId);
  delete tabData[tabId];
});

function isSkipped(url) {
  return (
    url.startsWith("chrome://") ||
    url.startsWith("chrome-extension://") ||
    url.startsWith("about:") ||
    url.startsWith("http://localhost") ||
    url.startsWith("http://127.0.0.1")
  );
}

function flushTab(tabId) {
  const data = tabData[tabId];
  if (!data || !data.url || isSkipped(data.url)) return;

  const timeSpent = Math.floor((Date.now() - data.startTime) / 1000);
  if (timeSpent < 3) return; // skip flash navigations

  fetch(ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      url: data.url,
      title: data.title,
      time_spent_seconds: timeSpent,
      timestamp: Date.now(),
    }),
  }).catch(() => {
    // Server not running — silently ignore
  });
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || typeof message !== "object") return false;

  if (message.type === "TRACK_CONTEXT_EVENT") {
    postContextEvent(message.event || {})
      .then((result) => sendResponse(result))
      .catch((error) => sendResponse({status: "error", error: String(error)}));
    return true;
  }

  if (message.type === "REQUEST_CONTEXT_BUNDLE") {
    requestContextBundle(message.request || {})
      .then((bundle) => {
        if (sender.tab && sender.tab.id) {
          chrome.tabs.sendMessage(sender.tab.id, {type: "INJECT_OVERLAY", bundle}, () => {});
        }
        sendResponse({status: "ok", bundle});
      })
      .catch((error) => sendResponse({status: "error", error: String(error)}));
    return true;
  }

  if (message.type === "CONTEXT_HEARTBEAT") {
    postHeartbeat(message.context || {})
      .then((result) => sendResponse(result))
      .catch((error) => sendResponse({status: "error", error: String(error)}));
    return true;
  }

  return false;
});

async function postContextEvent(event) {
  const payload = {
    app_id: String(event.app_id || ""),
    feature_id: String(event.feature_id || ""),
    action: String(event.action || ""),
    session_id: String(event.session_id || ""),
    user_id: String(event.user_id || "local_user"),
    timestamp: Number(event.timestamp || Date.now()),
  };

  const response = await fetch(CONTEXT_EVENT_ENDPOINT, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  });
  return response.json();
}

async function requestContextBundle(request) {
  const response = await fetch(CONTEXT_BUNDLE_ENDPOINT, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      app_id: String(request.app_id || ""),
      user_id: String(request.user_id || "local_user"),
      intent: String(request.intent || "adapt_ui"),
      requested_scopes: Array.isArray(request.requested_scopes) ? request.requested_scopes : [],
    }),
  });
  return response.json();
}

async function postHeartbeat(context) {
  const response = await fetch(CONTEXT_HEARTBEAT_ENDPOINT, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      user_id: String(context.user_id || "local_user"),
      project: String(context.project || ""),
      active_apps: Array.isArray(context.active_apps) ? context.active_apps : [],
      inferred_intent: String(context.inferred_intent || ""),
      session_depth: String(context.session_depth || "shallow"),
    }),
  });
  return response.json();
}
