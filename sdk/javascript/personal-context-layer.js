export class PersonalContextLayer {
  constructor({
    appId,
    baseUrl = "http://127.0.0.1:7823",
    apiKey = "",
    userToken = "",
    fetchImpl = globalThis.fetch,
  } = {}) {
    if (!appId) {
      throw new Error("appId is required");
    }
    if (!fetchImpl) {
      throw new Error("fetch is required");
    }
    this.appId = appId;
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.apiKey = apiKey;
    this.userToken = userToken;
    this.fetch = fetchImpl;
  }

  registerApp({ name, allowedLayers }) {
    return this.post("/pcl/apps", {
      app_id: this.appId,
      name,
      allowed_layers: allowedLayers,
    });
  }

  trackFeature({
    userId,
    featureId,
    featureName = "",
    eventType = "used",
    weight = 1.0,
    timestamp = Date.now(),
  }) {
    return this.post("/pcl/events/feature", {
      app_id: this.appId,
      user_id: userId,
      feature_id: featureId,
      feature_name: featureName,
      event_type: eventType,
      weight,
      timestamp,
    });
  }

  track({
    userId = "local_user",
    featureId,
    action = "used",
    sessionId = "",
    timestamp = Date.now(),
    isSynthetic = false,
    metadata = {},
  }) {
    if (!featureId) {
      throw new Error("featureId is required");
    }
    return this.post("/v1/ingest/sdk", {
      app_id: this.appId,
      user_id: userId,
      feature_id: normalizeFeatureId(featureId),
      action,
      session_id: sessionId,
      timestamp,
      is_synthetic: isSynthetic,
      metadata,
    });
  }

  generateColdStart({
    userId = "local_user",
    appName = this.appId,
    features = [],
    role = "",
    domain = "",
    skillLevel = "intermediate",
  } = {}) {
    return this.post("/v1/context/cold-start", {
      app_id: this.appId,
      app_name: appName,
      user_id: userId,
      features,
      role,
      domain,
      skill_level: skillLevel,
    });
  }

  personalize({
    userId,
    features,
    requestedLayers = [],
    purpose = "ui_personalization",
  }) {
    return this.post("/pcl/query", {
      app_id: this.appId,
      user_id: userId,
      purpose,
      requested_layers: requestedLayers,
      features,
    });
  }

  getContextBundle({
    userId = "local_user",
    intent = "full_profile",
    requestedScopes = [],
  } = {}) {
    return this.post("/v1/context/bundle", {
      app_id: this.appId,
      user_id: userId,
      intent,
      requested_scopes: requestedScopes,
    });
  }

  getSharedBundle({userId = "local_user"} = {}) {
    const params = new URLSearchParams({user_id: userId});
    return this.get(`/v1/context/shared-bundle?${params.toString()}`);
  }

  grantWebDomain({
    userId = "local_user",
    domain,
    scopes = ["getFeatureUsage", "track"],
  } = {}) {
    if (!domain) {
      throw new Error("domain is required");
    }
    return this.post("/v1/web/permissions", {
      user_id: userId,
      domain,
      scopes,
    });
  }

  checkWebDomain({
    userId = "local_user",
    domain,
    requestedScopes = [],
  } = {}) {
    if (!domain) {
      throw new Error("domain is required");
    }
    return this.post("/v1/web/permissions/check", {
      user_id: userId,
      domain,
      requested_scopes: requestedScopes,
    });
  }

  revokeWebDomain({userId = "local_user", domain} = {}) {
    if (!domain) {
      throw new Error("domain is required");
    }
    const params = new URLSearchParams({user_id: userId});
    return this.delete(`/v1/web/permissions/${encodeURIComponent(domain)}?${params.toString()}`);
  }

  listIntegrationOAuthTokens({userId = "local_user"} = {}) {
    const params = new URLSearchParams({user_id: userId});
    return this.get(`/pcl/integrations/oauth/tokens?${params.toString()}`);
  }

  revokeIntegrationOAuthToken({userId = "local_user", source} = {}) {
    if (!source) {
      throw new Error("source is required");
    }
    const params = new URLSearchParams({user_id: userId});
    return this.delete(`/pcl/integrations/${encodeURIComponent(source)}/oauth/token?${params.toString()}`);
  }

  registerPushToken({
    userId = "local_user",
    deviceId,
    apnsToken,
    platform = "ios",
    environment = "development",
  } = {}) {
    if (!deviceId) {
      throw new Error("deviceId is required");
    }
    if (!apnsToken) {
      throw new Error("apnsToken is required");
    }
    return this.post("/v1/devices/push-token", {
      user_id: userId,
      device_id: deviceId,
      apns_token: apnsToken,
      platform,
      environment,
    });
  }

  listPushTokens({userId = "local_user", activeOnly = true} = {}) {
    const params = new URLSearchParams({
      user_id: userId,
      active_only: String(activeOnly),
    });
    return this.get(`/v1/devices/push-token?${params.toString()}`);
  }

  revokePushToken({userId = "local_user", deviceId} = {}) {
    if (!deviceId) {
      throw new Error("deviceId is required");
    }
    const params = new URLSearchParams({user_id: userId});
    return this.delete(`/v1/devices/push-token/${encodeURIComponent(deviceId)}?${params.toString()}`);
  }

  listNotificationRoutes({userId = "local_user", limit = 100} = {}) {
    const params = new URLSearchParams({
      user_id: userId,
      limit: String(limit),
    });
    return this.get(`/v1/notifications/routes?${params.toString()}`);
  }

  heartbeat({
    userId = "local_user",
    project = "",
    activeApps = [this.appId],
    inferredIntent = "",
    sessionDepth = "shallow",
  } = {}) {
    return this.post("/v1/context/heartbeat", {
      user_id: userId,
      project,
      active_apps: activeApps,
      inferred_intent: inferredIntent,
      session_depth: sessionDepth,
    });
  }

  feedback({
    userId = "local_user",
    bundleId,
    outcome,
    featuresActuallyUsed = [],
  }) {
    if (!bundleId) {
      throw new Error("bundleId is required");
    }
    if (!outcome) {
      throw new Error("outcome is required");
    }
    return this.post("/v1/context/feedback", {
      app_id: this.appId,
      user_id: userId,
      bundle_id: bundleId,
      outcome,
      features_actually_used: featuresActuallyUsed.map(normalizeFeatureId),
    });
  }

  activity({userId = "local_user", limit = 100} = {}) {
    const params = new URLSearchParams({user_id: userId, limit: String(limit)});
    return this.get(`/v1/context/activity?${params.toString()}`);
  }

  revokeApp() {
    return this.post(`/pcl/apps/${this.appId}/revoke`, {});
  }

  deleteAppData() {
    return this.delete(`/pcl/apps/${this.appId}/data`);
  }

  clearQueryLog({userId} = {}) {
    const params = new URLSearchParams({app_id: this.appId});
    if (userId) {
      params.set("user_id", userId);
    }
    return this.delete(`/pcl/query-log?${params.toString()}`);
  }

  deleteUserData({userId}) {
    if (!userId) {
      throw new Error("userId is required");
    }
    return this.delete(`/pcl/users/${encodeURIComponent(userId)}/data`);
  }

  deleteAllContext({userId = "local_user"} = {}) {
    const params = new URLSearchParams({user_id: userId});
    return this.delete(`/v1/context/all?${params.toString()}`);
  }

  async get(path) {
    const response = await this.fetch(`${this.baseUrl}${path}`, {
      method: "GET",
      headers: this.headers(),
    });
    const data = await response.json();
    if (!response.ok) {
      const error = new Error(data?.error || `PCL request failed: ${response.status}`);
      error.response = data;
      throw error;
    }
    return data;
  }

  async post(path, payload) {
    const response = await this.fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: this.headers({"Content-Type": "application/json"}),
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      const error = new Error(data?.error || `PCL request failed: ${response.status}`);
      error.response = data;
      throw error;
    }
    return data;
  }

  async delete(path) {
    const response = await this.fetch(`${this.baseUrl}${path}`, {
      method: "DELETE",
      headers: this.headers(),
    });
    const data = await response.json();
    if (!response.ok) {
      const error = new Error(data?.error || `PCL request failed: ${response.status}`);
      error.response = data;
      throw error;
    }
    return data;
  }

  headers(extra = {}) {
    const headers = {...extra};
    if (this.apiKey) {
      headers.Authorization = `Bearer ${this.apiKey}`;
    }
    if (this.userToken) {
      headers["x-user-token"] = this.userToken;
    }
    return headers;
  }
}

export function isAvailable({documentRef = globalThis.document} = {}) {
  return documentRef?.documentElement?.getAttribute("data-cl-ext") === "1";
}

export async function getBundle({
  appId = globalThis.location?.hostname || "",
  userId = "local_user",
  intent = "adapt_ui",
  requestedScopes = ["getFeatureUsage"],
  timeoutMs = 1000,
  windowRef = globalThis.window,
  documentRef = globalThis.document,
  allowLocalhostFallback = false,
  localhostBaseUrl = "http://127.0.0.1:7432",
  fetchImpl = globalThis.fetch,
} = {}) {
  if (!isAvailable({documentRef}) || !windowRef?.postMessage) {
    if (allowLocalhostFallback) {
      return localBundleRequest({
        appId,
        userId,
        intent,
        requestedScopes,
        localhostBaseUrl,
        fetchImpl,
      });
    }
    return null;
  }
  return postBridgeRequest({
    windowRef,
    timeoutMs,
    requestType: "CL_GET_BUNDLE",
    responseType: "CL_BUNDLE_RESPONSE",
    payload: {
      appId,
      intent,
      requestedScopes,
    },
  });
}

export async function track({
  appId = globalThis.location?.hostname || "",
  userId = "local_user",
  featureId,
  action = "used",
  sessionId = "",
  timestamp = Date.now(),
  metadata = {},
  timeoutMs = 1000,
  windowRef = globalThis.window,
  documentRef = globalThis.document,
  allowLocalhostFallback = false,
  localhostBaseUrl = "http://127.0.0.1:7432",
  fetchImpl = globalThis.fetch,
} = {}) {
  if (!featureId) {
    throw new Error("featureId is required");
  }
  if (!isAvailable({documentRef}) || !windowRef?.postMessage) {
    if (allowLocalhostFallback) {
      return localTrackRequest({
        appId,
        userId,
        featureId: normalizeFeatureId(featureId),
        action,
        sessionId,
        timestamp,
        metadata,
        localhostBaseUrl,
        fetchImpl,
      });
    }
    return null;
  }
  return postBridgeRequest({
    windowRef,
    timeoutMs,
    requestType: "CL_TRACK",
    responseType: "CL_TRACK_RESPONSE",
    payload: {
      appId,
      featureId: normalizeFeatureId(featureId),
      action,
      sessionId,
      timestamp,
      metadata,
    },
  });
}

function normalizeFeatureId(featureId) {
  return String(featureId)
    .toLowerCase()
    .replace(/^[a-z0-9-]+:/, "")
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function postBridgeRequest({
  windowRef,
  timeoutMs,
  requestType,
  responseType,
  payload,
}) {
  const requestId = cryptoRandomId();
  return new Promise((resolve) => {
    const timer = setTimeout(() => {
      cleanup();
      resolve(null);
    }, timeoutMs);
    function cleanup() {
      clearTimeout(timer);
      windowRef.removeEventListener("message", onMessage);
    }
    function onMessage(event) {
      if (event.source && event.source !== windowRef) return;
      const data = event.data || {};
      if (data.type !== responseType || data.requestId !== requestId) return;
      cleanup();
      if (data.error) {
        resolve(null);
        return;
      }
      resolve(data.bundle || data.result || null);
    }
    windowRef.addEventListener("message", onMessage);
    windowRef.postMessage({
      type: requestType,
      requestId,
      ...payload,
    }, "*");
  });
}

async function localBundleRequest({
  appId,
  userId,
  intent,
  requestedScopes,
  localhostBaseUrl,
  fetchImpl,
}) {
  if (!fetchImpl) return null;
  try {
    const response = await fetchImpl(`${localhostBaseUrl.replace(/\/+$/, "")}/v1/context/bundle`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        app_id: appId,
        user_id: userId,
        intent,
        requested_scopes: requestedScopes,
      }),
    });
    if (!response.ok) return null;
    return response.json();
  } catch (_) {
    return null;
  }
}

async function localTrackRequest({
  appId,
  userId,
  featureId,
  action,
  sessionId,
  timestamp,
  metadata,
  localhostBaseUrl,
  fetchImpl,
}) {
  if (!fetchImpl) return null;
  try {
    const response = await fetchImpl(`${localhostBaseUrl.replace(/\/+$/, "")}/v1/ingest/extension`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        app_id: appId,
        user_id: userId,
        feature_id: featureId,
        action,
        session_id: sessionId,
        timestamp,
        metadata,
      }),
    });
    if (!response.ok) return null;
    return response.json();
  } catch (_) {
    return null;
  }
}

function cryptoRandomId() {
  const cryptoRef = globalThis.crypto;
  if (cryptoRef?.randomUUID) {
    return cryptoRef.randomUUID();
  }
  return `cl_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}
