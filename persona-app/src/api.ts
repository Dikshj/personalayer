const SESSION_STORAGE_KEY = "personalayer_session_token";
const rawApiBase = import.meta.env.VITE_PERSONALAYER_API_BASE || (import.meta.env.DEV ? "http://127.0.0.1:7823" : "");
export const API_BASE = rawApiBase.replace(/\/$/, "");
function readBool(value: unknown, fallback: boolean): boolean {
  if (value === undefined || value === null || value === "") return fallback;
  return !["0", "false", "no", "off"].includes(String(value).toLowerCase());
}

export const API_CONFIG = {
  apiBase: API_BASE,
  hasApiBase: Boolean(API_BASE),
  isProduction: import.meta.env.PROD,
  // Defaults to required in production; the env var can force it on/off.
  requiresSession: readBool(import.meta.env.VITE_PERSONALAYER_REQUIRE_SESSION, import.meta.env.PROD),
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
  localStorage.removeItem(SESSION_META_KEY);
}

// Session metadata (user + expiry) tracked locally. The backend issues a 7-day
// session; we record the expiry so the UI can warn and the guard can redirect.
const SESSION_META_KEY = "personalayer_session_meta";
const SESSION_TTL_MS = 7 * 24 * 60 * 60 * 1000;

export type SessionMeta = { user_id: string; created_at: number; expires_at: number };

export function storeSessionMeta(userId: string) {
  const now = Date.now();
  const meta: SessionMeta = { user_id: userId, created_at: now, expires_at: now + SESSION_TTL_MS };
  localStorage.setItem(SESSION_META_KEY, JSON.stringify(meta));
}

export function getSessionMeta(): SessionMeta | null {
  try {
    const raw = localStorage.getItem(SESSION_META_KEY);
    return raw ? (JSON.parse(raw) as SessionMeta) : null;
  } catch {
    return null;
  }
}

export function isSessionExpired(): boolean {
  const meta = getSessionMeta();
  return Boolean(meta?.expires_at && Date.now() > meta.expires_at);
}

export type BackendStatus = "loading" | "online" | "offline";

// ---- Cross-device sync types ------------------------------------------------

export type Keypair = {
  algorithm?: string;
  public_key: string;
  private_key: string;
};

export type TransferEnvelope = {
  schema?: string;
  ephemeral_public_key?: string;
  nonce?: string;
  ciphertext?: string;
};

export type PairingSession = {
  id?: string;
  user_id?: string;
  requester_device_id?: string;
  requester_device_name?: string;
  requester_public_key?: string;
  approver_device_id?: string;
  approver_public_key?: string;
  pairing_code?: string;
  qr_payload?: Record<string, unknown>;
  requested_scopes?: string[];
  status?: string;
  expires_at?: number;
  approved_at?: string | null;
  claimed_at?: string | null;
  revoked_at?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type MergeResult = {
  updated?: number;
  scopes?: string[];
};

export type PairingApprovalResponse = {
  status?: string;
  session?: PairingSession;
  transfer_envelope?: TransferEnvelope;
  recovery_token?: string;
  error?: string;
};

export type PairingClaimResponse = {
  status?: string;
  session?: PairingSession;
  transfer_envelope?: TransferEnvelope;
  merged?: MergeResult;
  local_snapshot?: SyncSnapshot;
  error?: string;
};

export type SyncSnapshot = {
  id?: string;
  user_id?: string;
  device_id?: string;
  version?: string;
  parent_version?: string;
  summary_hash?: string;
  merge_status?: string;
  created_at?: string;
};

export type SyncConflict = {
  id?: string;
  user_id?: string;
  local_version?: string;
  remote_version?: string;
  reason?: string;
  status?: string;
  details?: Record<string, unknown>;
  created_at?: string;
  resolved_at?: string | null;
};

export type SyncAuditEvent = {
  id?: string;
  user_id?: string;
  action?: string;
  device_id?: string;
  version?: string;
  details?: Record<string, unknown>;
  created_at?: string | number;
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
  created_at?: string | number;
  timestamp?: number;
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
  auth_type?: string;
  connected?: boolean;
  items_synced?: number;
  last_sync_status?: string;
  last_sync_at?: string | number | null;
  account_hint?: string;
  error?: string;
  scopes?: string[];
  description?: string;
  oauth?: Record<string, unknown> | null;
  metadata_example?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  connected_at?: string | null;
  disconnected_at?: string | null;
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

export const DEFAULT_PAIRING_SCOPES = [
  "profile_summary",
  "preferences",
  "feature_signals",
  "memory_summaries",
];

// Generates an ephemeral X25519 keypair on the backend. The private key is
// returned once; native clients should persist it in the OS keychain. The web
// client keeps it in localStorage for this browser device only.
export async function generateKeypair(): Promise<Keypair> {
  return postJson("/v1/sync/keypair", {});
}

const KEYPAIR_STORAGE_KEY = "personalayer_sync_keypair";
const DEVICE_NAME_KEY = "personalayer_web_device_name";

export function getWebDeviceId(): string {
  return `web-${getStableDeviceId()}`;
}

// Registers this browser as a trusted sync device (ensuring it has a keypair).
export async function rememberBrowserAsDevice(): Promise<{ status?: string; device?: SyncDevice; error?: string }> {
  const keypair = await ensureWebKeypair();
  return registerSyncDevice({
    device_id: getWebDeviceId(),
    device_name: getWebDeviceName(),
    public_key: keypair.public_key,
  });
}

export function getWebDeviceName(): string {
  const stored = localStorage.getItem(DEVICE_NAME_KEY);
  if (stored) return stored;
  const ua = typeof navigator !== "undefined" ? navigator.userAgent : "";
  const guess = /Mobi|Android|iPhone|iPad/.test(ua) ? "PersonaLayer Mobile Web" : "PersonaLayer Web";
  return guess;
}

export function setWebDeviceName(name: string) {
  const value = name.trim();
  if (value) localStorage.setItem(DEVICE_NAME_KEY, value);
  else localStorage.removeItem(DEVICE_NAME_KEY);
}

export function getStoredKeypair(): Keypair | null {
  try {
    const raw = localStorage.getItem(KEYPAIR_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Keypair;
    return parsed.public_key && parsed.private_key ? parsed : null;
  } catch {
    return null;
  }
}

// Returns this browser's sync keypair, generating and persisting one on first
// use. Only the public key is ever displayed; the private key stays local.
export async function ensureWebKeypair(forceRotate = false): Promise<Keypair> {
  if (!forceRotate) {
    const existing = getStoredKeypair();
    if (existing) return existing;
  }
  const keypair = await generateKeypair();
  localStorage.setItem(KEYPAIR_STORAGE_KEY, JSON.stringify(keypair));
  return keypair;
}

export function clearStoredKeypair() {
  localStorage.removeItem(KEYPAIR_STORAGE_KEY);
}

// Requester side: start a pairing session from this browser device. Uses (and
// persists) this device's keypair so the later claim step can decrypt.
export async function startPairingSession(
  scopes: string[] = DEFAULT_PAIRING_SCOPES,
): Promise<{ status: string; session?: PairingSession; qr_payload?: Record<string, unknown>; error?: string }> {
  const keypair = await ensureWebKeypair();
  return postJson("/v1/sync/pairing/start", {
    requester_device_id: getWebDeviceId(),
    requester_device_name: getWebDeviceName(),
    requester_public_key: keypair.public_key,
    requested_scopes: scopes,
    ttl_seconds: 600,
  });
}

export async function getPairingSession(
  sessionId: string,
): Promise<{ status: string; session?: PairingSession }> {
  return getJson(`/v1/sync/pairing/${encodeURIComponent(sessionId)}?user_id=local_user`);
}

// Approver side: approve an incoming requester by pairing code or session id.
// Reuses this browser's keypair as the approver key. Returns the one-time
// recovery token, which must be shown to the user only once.
export async function approvePairing(opts: {
  pairingCode?: string;
  sessionId?: string;
  approverDeviceName?: string;
}): Promise<PairingApprovalResponse> {
  const keypair = await ensureWebKeypair();
  return postJson("/v1/sync/pairing/approve", {
    user_id: "local_user",
    pairing_code: opts.pairingCode || "",
    session_id: opts.sessionId || "",
    approver_device_id: getWebDeviceId(),
    approver_device_name: opts.approverDeviceName || getWebDeviceName(),
    approver_public_key: keypair.public_key,
  });
}

// Requester side: claim the encrypted transfer once the session is approved.
export async function claimPairing(sessionId: string): Promise<PairingClaimResponse> {
  const keypair = getStoredKeypair();
  return postJson(`/v1/sync/pairing/${encodeURIComponent(sessionId)}/claim`, {
    user_id: "local_user",
    requester_device_id: getWebDeviceId(),
    requester_private_key: keypair?.private_key || "",
  });
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

export async function editSignal(
  signalId: number,
  patch: { name?: string; confidence?: number; shareable?: boolean; evidence?: string; weight?: number; reason?: string },
): Promise<PersonaSignal> {
  const { reason, ...rest } = patch;
  return patchJson(`/v1/control-center/signals/${signalId}`, {
    user_id: "local_user",
    reason: reason || "Edited from persona dashboard",
    ...rest,
  });
}

export async function getApps(): Promise<{ apps: PclApp[] }> {
  return getJson("/pcl/apps");
}

export async function getIntegrations(): Promise<{ integrations: PclIntegration[] }> {
  return getJson("/pcl/integrations");
}

export async function getIntegrationCatalog(): Promise<{ integrations: PclIntegration[] }> {
  return getJson("/pcl/integrations/catalog");
}

export async function connectIntegration(
  source: string,
  metadata: Record<string, unknown> = { connected_from: "persona_app" },
  accountHint = "",
): Promise<{ status?: string; integration?: PclIntegration }> {
  return postJson(`/pcl/integrations/${encodeURIComponent(source)}/connect`, {
    metadata,
    account_hint: accountHint,
    auth_status: "local_metadata",
  });
}

export async function disconnectIntegration(source: string): Promise<{ status?: string }> {
  return postJson(`/pcl/integrations/${encodeURIComponent(source)}/disconnect`, {});
}

export async function syncIntegration(
  source: string,
): Promise<{ source?: string; status?: string; items_synced?: number; error?: string | null; last_sync_at?: string }> {
  return postJson(`/pcl/integrations/${encodeURIComponent(source)}/sync`, {});
}

// ---- OAuth connector lifecycle ----------------------------------------------

export type OAuthStartResponse = {
  status?: string; // "ok" | "configuration_required" | "error"
  source?: string;
  state?: string;
  auth_url?: string;
  client_id_env?: string;
  redirect_uri?: string;
  error?: string;
};

export async function startOAuth(source: string, redirectUri: string): Promise<OAuthStartResponse> {
  return postJson(`/pcl/integrations/${encodeURIComponent(source)}/oauth/start`, {
    user_id: "local_user",
    redirect_uri: redirectUri,
  });
}

export async function completeOAuthCallback(opts: {
  state: string;
  code: string;
  account_hint?: string;
}): Promise<{ status?: string; source?: string; integration?: PclIntegration; error?: string }> {
  return postJson("/pcl/integrations/oauth/callback", {
    state: opts.state,
    code: opts.code,
    account_hint: opts.account_hint || "",
  });
}

export async function refreshOAuth(source: string): Promise<{ status?: string; error?: string; expires_at?: number }> {
  return postJson(`/pcl/integrations/${encodeURIComponent(source)}/oauth/refresh?user_id=local_user`, {});
}

export async function revokeOAuthToken(source: string): Promise<{ status?: string }> {
  return deleteJson(`/pcl/integrations/${encodeURIComponent(source)}/oauth/token?user_id=local_user`);
}

export async function deleteIntegrationData(
  source: string,
): Promise<{ status?: string; deleted?: Record<string, number> }> {
  return deleteJson(`/pcl/integrations/${encodeURIComponent(source)}/data`);
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

export async function getBoundaries(activeOnly = true): Promise<{ user_id?: string; boundaries: PrivacyBoundary[] }> {
  return getJson(`/v1/user/boundaries?user_id=local_user&active_only=${activeOnly}`);
}

export async function deactivateBoundary(boundaryId: string): Promise<{ revoked?: boolean; boundary_id?: string }> {
  return postJson(`/v1/user/boundaries/${encodeURIComponent(boundaryId)}/deactivate?user_id=local_user`, {});
}

// ---- Context preview (what an app would receive) ----------------------------

export type ContextPreview = {
  id?: string;
  user_id?: string;
  app_id?: string;
  app_name?: string;
  requested_purpose?: string;
  permission_scope?: string[];
  allowed_fields?: string[];
  excluded_fields?: string[];
  confidence_levels?: Record<string, number>;
  plain_english_summary?: string;
  preview_json?: Record<string, unknown>;
  status?: string;
  user_decision?: string;
  narrowed_fields?: string[];
  created_at?: string;
  decided_at?: string | null;
};

export const CONTEXT_LAYERS = [
  "identity_role",
  "capability_signals",
  "behavior_patterns",
  "active_context",
  "explicit_preferences",
];

export async function createContextPreview(opts: {
  app_id: string;
  app_name?: string;
  requested_purpose?: string;
  requested_layers?: string[];
  requested_scopes?: string[];
}): Promise<ContextPreview> {
  return postJson("/v1/context/preview", {
    user_id: "local_user",
    app_id: opts.app_id,
    app_name: opts.app_name || "",
    requested_purpose: opts.requested_purpose || "",
    requested_layers: opts.requested_layers || CONTEXT_LAYERS,
    requested_scopes: opts.requested_scopes || [],
  });
}

export async function getContextPreview(previewId: string): Promise<ContextPreview> {
  return getJson(`/v1/context/preview/${encodeURIComponent(previewId)}`);
}

export async function decideContextPreview(
  previewId: string,
  decision: "approved" | "denied" | "narrowed",
  narrowedFields: string[] = [],
): Promise<ContextPreview> {
  return postJson(`/v1/context/preview/${encodeURIComponent(previewId)}/decision`, {
    decision,
    narrowed_fields: narrowedFields,
  });
}

// ---- Control-center: permissions, audit, export -----------------------------

export type ControlCenterPermission = {
  id?: string;
  app_id?: string;
  name?: string;
  permission_type?: string;
  type?: string;
  status?: string;
  scopes?: string[];
  granted_at?: string | number;
  expires_at?: string | number | null;
};

export type AuditEntry = {
  id?: string;
  action?: string;
  target_type?: string;
  target_id?: string;
  details?: Record<string, unknown>;
  created_at?: string | number;
};

export type SyncDevice = {
  id?: string;
  user_id?: string;
  device_id?: string;
  device_name?: string;
  public_key?: string;
  trust_status?: string;
  last_seen_at?: string | number | null;
  created_at?: string | number;
  revoked_at?: string | number | null;
};

export async function getControlCenterPermissions(): Promise<{
  all_permissions?: ControlCenterPermission[];
  active?: ControlCenterPermission[];
  revoked?: ControlCenterPermission[];
  expired?: ControlCenterPermission[];
  counts?: Record<string, number>;
}> {
  return getJson("/v1/control-center/permissions?user_id=local_user");
}

export async function revokeControlCenterPermission(
  permissionId: string,
  permissionType: string,
): Promise<Record<string, unknown>> {
  return postJson(`/v1/control-center/permissions/${encodeURIComponent(permissionId)}/revoke`, {
    user_id: "local_user",
    permission_type: permissionType,
  });
}

export async function getAuditLog(limit = 100): Promise<{ logs: AuditEntry[]; count: number }> {
  return getJson(`/v1/control-center/audit?user_id=local_user&limit=${limit}`);
}

// ---- App context-request log (query_logs) -----------------------------------

export type QueryLogEntry = {
  id?: string;
  app_id?: string;
  user_id?: string;
  purpose?: string;
  requested_layers?: string[];
  returned_layers?: string[];
  feature_ids?: string[];
  status?: string; // "returned" | "denied"
  reason?: string;
  created_at?: string | number;
};

export async function getQueryLog(opts: { app_id?: string; limit?: number } = {}): Promise<{ logs: QueryLogEntry[] }> {
  const params = new URLSearchParams();
  if (opts.app_id) params.set("app_id", opts.app_id);
  params.set("limit", String(opts.limit ?? 200));
  return getJson(`/pcl/query-log?${params.toString()}`);
}

export async function clearQueryLog(appId?: string): Promise<{ status?: string; deleted?: Record<string, number> }> {
  const params = new URLSearchParams({ user_id: "local_user" });
  if (appId) params.set("app_id", appId);
  return deleteJson(`/pcl/query-log?${params.toString()}`);
}

export async function getPrivacyDrops(limit = 100): Promise<{ drops: Array<Record<string, unknown>> }> {
  return getJson(`/v1/context/privacy-drops?user_id=local_user&limit=${limit}`);
}

export async function getSyncDevices(): Promise<{ user_id?: string; devices: SyncDevice[] }> {
  return getJson("/v1/sync/devices?user_id=local_user");
}

export async function registerSyncDevice(opts: {
  device_id: string;
  device_name?: string;
  public_key?: string;
  requested_scopes?: string[];
}): Promise<{ status?: string; device?: SyncDevice; error?: string }> {
  return postJson("/v1/sync/devices", { user_id: "local_user", ...opts });
}

export async function trustSyncDevice(
  deviceId: string,
  opts: { device_name?: string; public_key?: string } = {},
): Promise<{ status?: string; device?: SyncDevice; error?: string }> {
  return postJson(`/v1/sync/devices/${encodeURIComponent(deviceId)}/trust`, {
    user_id: "local_user",
    ...opts,
  });
}

export async function revokeSyncDevice(
  deviceId: string,
): Promise<{ status?: string; device?: SyncDevice; error?: string }> {
  return postJson(`/v1/sync/devices/${encodeURIComponent(deviceId)}/revoke`, { user_id: "local_user" });
}

export async function rotateSyncDeviceKey(
  deviceId: string,
  publicKey: string,
  recoveryToken = "",
): Promise<{ status?: string; device?: SyncDevice; error?: string }> {
  return postJson(`/v1/sync/devices/${encodeURIComponent(deviceId)}/rotate-key`, {
    user_id: "local_user",
    public_key: publicKey,
    recovery_token: recoveryToken,
  });
}

export async function recoveryRevokeSyncDevice(
  deviceId: string,
  reason = "",
): Promise<{ status?: string; device?: SyncDevice; error?: string }> {
  return postJson(`/v1/sync/devices/${encodeURIComponent(deviceId)}/recovery-revoke`, {
    user_id: "local_user",
    reason,
  });
}

// ---- Snapshots, import, conflicts, sync audit -------------------------------

export async function createSyncSnapshot(): Promise<{
  status?: string;
  snapshot?: SyncSnapshot;
  encrypted_blob?: string;
  error?: string;
}> {
  return postJson("/v1/sync/snapshot", {
    user_id: "local_user",
    device_id: getWebDeviceId(),
    device_name: getWebDeviceName(),
  });
}

export async function importSyncSnapshot(opts: {
  remote_device_id: string;
  encrypted_blob: string;
  expected_parent_version?: string | null;
}): Promise<{
  status?: string;
  snapshot?: SyncSnapshot;
  conflict?: SyncConflict;
  merged?: MergeResult;
  error?: string;
}> {
  return postJson("/v1/sync/import", { user_id: "local_user", ...opts });
}

export async function compactSnapshots(
  keepPerDevice = 5,
): Promise<{ user_id?: string; keep_per_device?: number; deleted?: number }> {
  return postJson("/v1/sync/snapshots/compact", {
    user_id: "local_user",
    keep_per_device: keepPerDevice,
  });
}

export async function getSyncConflicts(
  status = "open",
  limit = 100,
): Promise<{ user_id?: string; conflicts: SyncConflict[] }> {
  return getJson(`/v1/sync/conflicts?user_id=local_user&status=${encodeURIComponent(status)}&limit=${limit}`);
}

export async function resolveSyncConflict(
  conflictId: string,
  action: "accept_remote" | "keep_local" | "ignore",
): Promise<{ status?: string; resolution?: string; merged?: MergeResult; conflict?: SyncConflict; error?: string }> {
  return postJson(`/v1/sync/conflicts/${encodeURIComponent(conflictId)}/resolve`, {
    user_id: "local_user",
    action,
    device_id: getWebDeviceId(),
  });
}

export async function getSyncAudit(limit = 100): Promise<{ user_id?: string; audit: SyncAuditEvent[] }> {
  return getJson(`/v1/sync/audit?user_id=local_user&limit=${limit}`);
}

export async function exportControlCenterData(): Promise<Record<string, unknown>> {
  return postJson("/v1/control-center/export?user_id=local_user&format=json", {});
}

export async function deleteAllContext(): Promise<Record<string, unknown>> {
  return deleteJson("/v1/context/all?user_id=local_user");
}

export async function deleteUserData(userId = "local_user"): Promise<Record<string, unknown>> {
  return deleteJson(`/pcl/users/${encodeURIComponent(userId)}/data`);
}

// Creates a local session token via the backend bootstrap flow. When the
// backend returns a token (non-production or RETURN_SESSION_TOKEN=1) it is
// stored for Bearer auth; otherwise the httpOnly cookie carries the session.
export async function createLocalSession(
  userId = "local_user",
  bootstrapToken = "",
): Promise<{ status?: string; user_id?: string; session_token?: string }> {
  return postJson("/v1/auth/local/session", { user_id: userId, bootstrap_token: bootstrapToken });
}

// ---- Onboarding (first-run persona seed) ------------------------------------

export type OnboardingSeedAnswers = {
  identity?: string;
  features?: string | string[];
  behavior?: string;
  active_context?: string;
  preferences?: string | string[];
};

// Seeds the first persona from the welcome wizard (role, goals, tools, focus).
export async function seedOnboarding(
  answers: OnboardingSeedAnswers,
): Promise<{ status?: string; user_id?: string; profile_seed?: Record<string, unknown> }> {
  return postJson("/pcl/onboarding/seed", { user_id: "local_user", answers });
}

export async function getOnboardingSeed(): Promise<{
  user_id?: string;
  answers?: Record<string, unknown>;
  profile_seed?: Record<string, unknown>;
  error?: string;
}> {
  return getJson("/pcl/onboarding/seed?user_id=local_user");
}

// Records the initial privacy posture and marks onboarding complete.
export async function submitOnboardingFlow(answers: Record<string, unknown>): Promise<PrivacyProfile> {
  return postJson("/v1/onboarding/flow", { user_id: "local_user", answers });
}

// ---- App consent (third-party scope approval) -------------------------------

export type AppConsent = {
  id?: string;
  user_id?: string;
  app_id?: string;
  developer_id?: string;
  scopes?: string[];
  granted_via?: string;
  is_active?: boolean;
  granted_at?: string;
  revoked_at?: string | null;
};

export async function getApp(appId: string): Promise<PclApp | undefined> {
  const { apps } = await getApps();
  return apps.find((a) => a.app_id === appId);
}

export async function getConsents(): Promise<{ user_id?: string; permissions: AppConsent[] }> {
  return getJson("/v1/auth/consent?user_id=local_user");
}

export async function grantConsent(opts: {
  app_id: string;
  scopes: string[];
  granted_via?: string;
  developer_id?: string;
}): Promise<{ status?: string; permission?: AppConsent }> {
  return postJson("/v1/auth/consent", {
    user_id: "local_user",
    app_id: opts.app_id,
    scopes: opts.scopes,
    granted_via: opts.granted_via || "explicit",
    developer_id: opts.developer_id || "",
  });
}

export async function revokeConsent(appId: string): Promise<{ status?: string }> {
  return deleteJson(`/v1/auth/consent/${encodeURIComponent(appId)}?user_id=local_user`);
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
