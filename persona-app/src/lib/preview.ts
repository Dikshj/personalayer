// Illustrative preview data shown when the backend is unavailable, so the
// product surface is visible with a "Backend offline" notice. Not real data.

import type {
  AuditEntry,
  ControlCenterPermission,
  PclIntegration,
  PersonaSignal,
  PrivacyBoundary,
  SyncAuditEvent,
  SyncConflict,
  SyncDevice,
} from "../api";

const now = Date.now();
const hoursAgo = (h: number) => now - h * 3600_000;

export const previewSignals: PersonaSignal[] = [
  { id: 1, name: "Works in software", signal_type: "work_domain", source: "github", confidence: 0.92, why_it_exists: "Noticed from frequent GitHub activity and repository metadata.", shareable: true },
  { id: 2, name: "Building a side project", signal_type: "task_pattern", source: "inferred", confidence: 0.78, why_it_exists: "Recent repositories, docs, and product planning notes.", shareable: true },
  { id: 3, name: "Prefers direct communication", signal_type: "preference", source: "inferred", confidence: 0.71, why_it_exists: "Learned from how you interact with AI assistants.", shareable: true },
  { id: 4, name: "TypeScript", signal_type: "skill", source: "connector", confidence: 0.88, why_it_exists: "Primary language across recent commits.", shareable: true },
  { id: 5, name: "Based in India", signal_type: "preference", source: "onboarding", confidence: 0.6, why_it_exists: "Used only for local defaults such as timezone and region.", shareable: false },
];

export const previewSummary: Record<string, unknown> = {
  active_permissions: 2,
  privacy_boundaries: 2,
  signals_count: 5,
};

export const previewIntegrations: PclIntegration[] = [
  { source: "github", name: "GitHub", status: "connected", connected: true, items_synced: 211, last_sync_status: "ok" },
  { source: "calendar", name: "Calendar", status: "connected", connected: true, items_synced: 64, last_sync_status: "ok" },
  { source: "notion", name: "Notion", status: "connected", connected: true, items_synced: 38, last_sync_status: "ok" },
  { source: "gmail", name: "Gmail", status: "available", connected: false },
  { source: "spotify", name: "Spotify", status: "available", connected: false },
  { source: "browser", name: "Browser History", status: "available", connected: false },
];

export const previewPermissions: ControlCenterPermission[] = [
  { id: "inbox_zero", app_id: "inbox_zero", name: "Inbox Zero", permission_type: "app", status: "active", scopes: ["behavior_patterns", "active_context"], granted_at: hoursAgo(240) },
  { id: "code_assistant", app_id: "code_assistant", name: "Code Assistant", permission_type: "app", status: "active", scopes: ["capability_signals", "active_context"], granted_at: hoursAgo(700) },
];

export const previewBoundaries: PrivacyBoundary[] = [
  { id: "b1", boundary_type: "never_share_field", target: "emails", reason: "User marked emails private", is_active: true },
  { id: "b2", boundary_type: "never_share_field", target: "location", reason: "User marked location private", is_active: true },
];

export const previewAudit: AuditEntry[] = [
  { id: "a1", action: "context_access", target_type: "app", target_id: "code_assistant", details: { intent: "rank_features", status: "returned" }, created_at: hoursAgo(1) },
  { id: "a2", action: "signal_hidden", target_type: "signal", target_id: "5", details: { reason: "Hidden from apps" }, created_at: hoursAgo(3) },
  { id: "a3", action: "privacy_drop", target_type: "category", target_id: "financial", details: { source: "gmail" }, created_at: hoursAgo(6) },
  { id: "a4", action: "integration_sync", target_type: "integration", target_id: "github", details: { items: 12 }, created_at: hoursAgo(9) },
  { id: "a5", action: "permission_revoked", target_type: "app", target_id: "old_app", details: {}, created_at: hoursAgo(50) },
];

export const previewDevices: SyncDevice[] = [
  {
    id: "d1",
    device_id: "iphone-15-pro",
    device_name: "iPhone 15 Pro",
    public_key: "preview-ios-public-key-aaaa",
    trust_status: "trusted",
    created_at: hoursAgo(400),
    last_seen_at: hoursAgo(2),
  },
  {
    id: "d2",
    device_id: "macbook-air",
    device_name: "MacBook Air",
    public_key: "preview-mac-public-key-bbbb",
    trust_status: "trusted",
    created_at: hoursAgo(900),
    last_seen_at: hoursAgo(26),
  },
  {
    id: "d3",
    device_id: "pixel-tablet",
    device_name: "Pixel Tablet",
    public_key: "preview-android-public-key-cccc",
    trust_status: "pending",
    created_at: hoursAgo(1),
    last_seen_at: hoursAgo(1),
  },
  {
    id: "d4",
    device_id: "old-laptop",
    device_name: "Old Laptop",
    public_key: "preview-old-public-key-dddd",
    trust_status: "revoked",
    created_at: hoursAgo(4000),
    last_seen_at: hoursAgo(800),
    revoked_at: hoursAgo(300),
  },
];

export const previewConflicts: SyncConflict[] = [];

export const previewSyncAudit: SyncAuditEvent[] = [
  { id: "s1", action: "snapshot_created", device_id: "web-local", version: "9f2a1c4d8e", details: {}, created_at: hoursAgo(1) },
  { id: "s2", action: "pairing_claimed", device_id: "iphone-15-pro", details: { scopes: ["profile_summary", "preferences"] }, created_at: hoursAgo(3) },
  { id: "s3", action: "pairing_approved", device_id: "iphone-15-pro", details: {}, created_at: hoursAgo(3) },
  { id: "s4", action: "device_trusted", device_id: "macbook-air", details: {}, created_at: hoursAgo(26) },
  { id: "s5", action: "device_revoked", device_id: "old-laptop", details: { reason: "lost device" }, created_at: hoursAgo(300) },
];
