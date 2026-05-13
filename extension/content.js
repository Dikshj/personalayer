// ContextLayer generic app recognizer.
// Tracks feature-level behavior only: app_id, feature_id, action, session_id, timestamp.

const CL_USER_ID = "local_user";
const CL_SESSION_ID = crypto.randomUUID ? crypto.randomUUID() : String(Date.now());
const CL_HOVER_MS = 1200;
const CL_HEARTBEAT_MS = 5 * 60 * 1000;

let clApp = null;
let clObserver = null;
let clHoverTimers = new WeakMap();

initContextLayer();

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === "INJECT_OVERLAY") {
    applyOverlay(message.bundle || {});
  }
});

async function initContextLayer() {
  const registry = await loadRegistry();
  clApp = matchCurrentApp(registry, location.hostname);
  if (!clApp) return;

  injectStyles();
  bindFeatureListeners();
  clObserver = new MutationObserver(() => bindFeatureListeners());
  clObserver.observe(document.documentElement, {childList: true, subtree: true});

  sendHeartbeat();
  setInterval(sendHeartbeat, CL_HEARTBEAT_MS);
  requestOverlay();
  window.addEventListener("popstate", requestOverlay);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      sendHeartbeat();
      requestOverlay();
    }
  });
}

async function loadRegistry() {
  try {
    const response = await fetch(chrome.runtime.getURL("app-registry.json"));
    return response.json();
  } catch (_) {
    return {};
  }
}

function matchCurrentApp(registry, hostname) {
  const host = hostname.replace(/^www\./, "");
  for (const [domain, config] of Object.entries(registry)) {
    if (host === domain || host.endsWith(`.${domain}`)) {
      return config;
    }
  }
  return null;
}

function bindFeatureListeners() {
  if (!clApp) return;

  for (const [featureId, feature] of Object.entries(clApp.features || {})) {
    const selector = feature.selector;
    if (!selector) continue;

    for (const element of document.querySelectorAll(selector)) {
      if (element.dataset.clBound === "true") continue;
      element.dataset.clBound = "true";
      element.dataset.clFeatureId = featureId;

      if (feature.action_map?.click) {
        element.addEventListener("click", () => {
          clearHoverTimer(element);
          trackFeature(featureId, feature.action_map.click);
        }, {capture: true, passive: true});
      }

      if (feature.action_map?.mouseover_without_click) {
        element.addEventListener("mouseenter", () => {
          clearHoverTimer(element);
          const timer = setTimeout(() => {
            trackFeature(featureId, feature.action_map.mouseover_without_click);
          }, CL_HOVER_MS);
          clHoverTimers.set(element, timer);
        }, {passive: true});

        element.addEventListener("mouseleave", () => clearHoverTimer(element), {passive: true});
      }
    }
  }
}

function clearHoverTimer(element) {
  const timer = clHoverTimers.get(element);
  if (timer) clearTimeout(timer);
  clHoverTimers.delete(element);
}

function trackFeature(featureId, action) {
  if (!clApp || !featureId || !action) return;

  chrome.runtime.sendMessage({
    type: "TRACK_CONTEXT_EVENT",
    event: {
      app_id: clApp.app_id,
      feature_id: normalizeFeatureId(featureId),
      action,
      session_id: CL_SESSION_ID,
      user_id: CL_USER_ID,
      timestamp: Date.now(),
    },
  });
}

function requestOverlay() {
  if (!clApp) return;
  chrome.runtime.sendMessage({
    type: "REQUEST_CONTEXT_BUNDLE",
    request: {
      app_id: clApp.app_id,
      user_id: CL_USER_ID,
      intent: "adapt_ui",
      requested_scopes: ["getFeatureUsage"],
    },
  });
}

function sendHeartbeat() {
  if (!clApp) return;
  chrome.runtime.sendMessage({
    type: "CONTEXT_HEARTBEAT",
    context: {
      user_id: CL_USER_ID,
      project: inferProject(),
      active_apps: [clApp.app_id],
      inferred_intent: inferIntentFromPath(),
      session_depth: inferSessionDepth(),
    },
  });
}

function applyOverlay(bundle) {
  if (!clApp) return;
  const features = new Set(bundle.features || []);
  const suppressed = new Set(bundle.suppressed_features || []);

  for (const [featureId, feature] of Object.entries(clApp.features || {})) {
    const normalized = normalizeFeatureId(featureId);
    for (const element of document.querySelectorAll(feature.selector)) {
      element.classList.toggle("cl-highlight", features.has(normalized));
      element.classList.toggle("cl-hidden", suppressed.has(normalized));
    }
  }

  renderOverlay(bundle);
}

function renderOverlay(bundle) {
  let overlay = document.getElementById("cl-overlay");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "cl-overlay";
    document.documentElement.appendChild(overlay);
  }

  const confidence = Math.round(Number(bundle.confidence || 0) * 100);
  overlay.textContent = `${clApp.app_id} context ${confidence}%`;
  overlay.dataset.style = bundle.style || "default";
}

function injectStyles() {
  if (document.getElementById("cl-styles")) return;
  const style = document.createElement("style");
  style.id = "cl-styles";
  style.textContent = `
    .cl-highlight {
      outline: 2px solid #1d9bf0 !important;
      outline-offset: 2px !important;
      box-shadow: 0 0 0 4px rgba(29, 155, 240, 0.18) !important;
    }
    .cl-hidden {
      opacity: 0.28 !important;
      filter: grayscale(0.8) !important;
    }
    #cl-overlay {
      position: fixed !important;
      right: 12px !important;
      bottom: 12px !important;
      z-index: 2147483647 !important;
      padding: 7px 9px !important;
      border: 1px solid rgba(15, 23, 42, 0.18) !important;
      border-radius: 6px !important;
      background: rgba(255, 255, 255, 0.94) !important;
      color: #0f172a !important;
      font: 12px/1.2 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
      box-shadow: 0 8px 24px rgba(15, 23, 42, 0.14) !important;
      pointer-events: none !important;
    }
  `;
  document.documentElement.appendChild(style);
}

function normalizeFeatureId(featureId) {
  return String(featureId)
    .toLowerCase()
    .replace(/^[a-z0-9-]+:/, "")
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function inferProject() {
  const title = document.title || "";
  return title.split(/[|\-–—]/)[0].trim().slice(0, 80);
}

function inferIntentFromPath() {
  const path = location.pathname.toLowerCase();
  if (path.includes("settings") || path.includes("preferences")) return "preferences";
  if (path.includes("search")) return "searched";
  if (path.includes("pull") || path.includes("issue")) return "reviewing";
  if (path.includes("roadmap") || path.includes("project")) return "planning";
  return "adapt_ui";
}

function inferSessionDepth() {
  const minutesOpen = (performance.now() || 0) / 60000;
  if (minutesOpen >= 25) return "deep-work";
  if (minutesOpen >= 8) return "moderate";
  return "shallow";
}
