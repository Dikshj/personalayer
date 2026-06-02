const SESSION_STORAGE_KEY = "personalayer_session_token";
const rawApiBase = import.meta.env.VITE_PERSONALAYER_API_BASE || (import.meta.env.DEV ? "http://127.0.0.1:7823" : "");
export const API_BASE = rawApiBase.replace(/\/$/, "");
export const API_CONFIG = {
  apiBase: API_BASE,
  hasApiBase: Boolean(API_BASE),
  isProduction: import.meta.env.PROD,
  requiresSession: import.meta.env.PROD || Boolean(import.meta.env.VITE_PERSONALAYER_REQUIRE_SESSION),
};

export function getStoredSessionToken(): string {
  return (
    import.meta.env.VITE_PERSONALAYER_SESSION_TOKEN ||
    localStorage.getItem(SESSION_STORAGE_KEY) ||
    ""
  ).trim();
}

export function storeSessionToken(token: string) {
  const value = token.trim();
  if (value) localStorage.setItem(SESSION_STORAGE_KEY, value);
  else localStorage.removeItem(SESSION_STORAGE_KEY);
}

export function clearSessionToken() {
  localStorage.removeItem(SESSION_STORAGE_KEY);
}

export type BackendStatus = "loading" | "online" | "offline";

export type PairingSession = {
  id?: string;
  pairing_code?: string;
  status?: string;
  expires_at?: number;
  requested_scopes?: string[];
  qr_payload?: Record<string, unknown>;
};

export type PersonaSignal = {
  id?: number;
  name?: string;
  source?: string;
  signal_type?: string;
  confidence?: number;
  weight?: number;
  evidence?: string;
  why_it_exists?: string;
  human_readable_source?: string;
  human_readable_type?: string;
  shareable?: boolean;
  currently_shareable?: boolean;
};

export type PclApp = {
  app_id?: string;
  name?: string;
  status?: string;
  allowed_layers?: string[];
  created_at?: string;
};

export type PclIntegration = {
  source?: string;
  name?: string;
  status?: string;
  auth_status?: string;
  connected?: boolean;
  items_synced?: number;
  last_sync_status?: string;
};

export type PrivacyBoundary = {
  id?: string;
  boundary_type?: string;
  target?: string;
  reason?: string;
  is_active?: boolean;
};

export type PrivacyProfile = {
  preferences?: {
    privacy_level?: string;
    sharing_default?: string;
    enabled_integrations?: string[];
    personalization_goals?: string[];
  };
  active_boundaries?: PrivacyBoundary[];
  boundary_count?: number;
  onboarding_completed?: boolean;
};

export async function getHealth(): Promise<{ status?: string }> {
  return getJson("/health");
}

export async function startPairingSession(): Promise<{ status: string; session?: PairingSession; qr_payload?: unknown }> {
  const keypair = await postJson<{ public_key: string }>("/v1/sync/keypair", {});
  return postJson("/v1/sync/pairing/start", {
    requester_device_id: `web-${getStableDeviceId()}`,
    requester_device_name: "PersonaLayer Web",
    requester_public_key: keypair.public_key,
    requested_scopes: ["profile_summary", "preferences", "feature_signals", "memory_summaries"],
    ttl_seconds: 600,
  });
}

export async function getPairingSession(sessionId: string): Promise<{ status: string; session?: PairingSession }> {
  return getJson(`/v1/sync/pairing/${encodeURIComponent(sessionId)}`);
}

export async function getControlCenterSummary(): Promise<Record<string, unknown>> {
  return getJson("/v1/control-center/summary");
}

export async function searchSignals(): Promise<{ signals: PersonaSignal[]; count: number }> {
  return postJson("/v1/control-center/signals/search", {
    user_id: "local_user",
    limit: 20,
    offset: 0,
  });
}

export async function updateSignalShareable(signalId: number, shareable: boolean): Promise<PersonaSignal> {
  return patchJson(`/v1/control-center/signals/${signalId}`, {
    user_id: "local_user",
    shareable,
    reason: shareable ? "Marked shareable from privacy manager UI" : "Hidden from privacy manager UI",
  });
}

export async function deleteSignal(signalId: number): Promise<{ deleted: boolean; signal_id: number }> {
  return deleteJson(`/v1/control-center/signals/${signalId}?user_id=local_user`);
}

export async function getApps(): Promise<{ apps: PclApp[] }> {
  return getJson("/pcl/apps");
}

export async function getIntegrations(): Promise<{ integrations: PclIntegration[] }> {
  return getJson("/pcl/integrations");
}

export async function connectIntegration(source: string): Promise<Record<string, unknown>> {
  return postJson(`/pcl/integrations/${encodeURIComponent(source)}/connect`, {
    metadata: { connected_from: "persona_app" },
    auth_status: "local_metadata",
  });
}

export async function disconnectIntegration(source: string): Promise<Record<string, unknown>> {
  return postJson(`/pcl/integrations/${encodeURIComponent(source)}/disconnect`, {});
}

export async function getPrivacyProfile(): Promise<PrivacyProfile> {
  return getJson("/v1/user/privacy-profile");
}

export async function addPrivacyBoundary(boundaryType: string, target: string, reason: string): Promise<PrivacyBoundary> {
  return postJson("/v1/user/boundaries", {
    user_id: "local_user",
    boundary_type: boundaryType,
    target,
    reason,
  });
}

export async function deletePrivacyBoundary(boundaryId: string): Promise<Record<string, unknown>> {
  return deleteJson(`/v1/user/boundaries/${encodeURIComponent(boundaryId)}?user_id=local_user`);
}

async function getJson<T>(path: string): Promise<T> {
  return requestJson(path, { method: "GET" });
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  return requestJson(path, { method: "POST", body: JSON.stringify(body) });
}

async function patchJson<T>(path: string, body: unknown): Promise<T> {
  return requestJson(path, { method: "PATCH", body: JSON.stringify(body) });
}

async function deleteJson<T>(path: string): Promise<T> {
  return requestJson(path, { method: "DELETE" });
}

async function requestJson<T>(path: string, init: RequestInit): Promise<T> {
  if (!API_BASE) {
    throw new Error("Production API is not configured. Set VITE_PERSONALAYER_API_BASE for the deployed frontend.");
  }
  const token = getStoredSessionToken();
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers || {}),
    },
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      detail = payload.detail || payload.error || detail;
    } catch {
      // Keep status text when the server does not return JSON.
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

function getStableDeviceId() {
  const key = "personalayer_web_device_id";
  const existing = localStorage.getItem(key);
  if (existing) return existing;
  const next = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : String(Date.now());
  localStorage.setItem(key, next);
  return next;
}
