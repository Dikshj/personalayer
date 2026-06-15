# Personal Layer — Threat Model & Security Review

**Version:** 1.0  
**Date:** 2026-05-18  
**Scope:** Architecture v4 (local-first, thin cloud)

---

## 1. Assets

| Asset | Location | Sensitivity |
|-------|----------|-------------|
| Raw event payloads | Local encrypted vault | High |
| Synthesized personas | Local SQLite (GRDB) | High |
| Knowledge graph nodes | Local SQLite (GRDB) | Medium-High |
| Embedding vectors | Local SQLite (GRDB) | Medium |
| OAuth tokens | OS keychain / Secure Enclave | Critical |
| Device encryption key | Secure Enclave / Keychain | Critical |
| Cloud consent metadata | Supabase (RLS-protected) | Low |
| APNs tokens | Supabase (truncated) | Medium |

---

## 2. Threats & Mitigations

### T1: Malicious app extracts raw data via context bundle

**Risk:** An approved app requests a context bundle and tries to reconstruct raw events from abstract attributes.

**Mitigation:**
- Egress filter scrubs all PII, credentials, and raw content before bundle serialization.
- `raw_content` and `raw_payload` keys are explicitly stripped.
- Abstract attributes are one-way summaries (e.g., "frequent traveler" not "visited Tokyo on 2026-03-15").

**Verification:** `tests/test_production_hardening.py::TestEgressPrivacy`

---

### T2: Compromised extension sends raw data to attacker

**Risk:** Browser extension is compromised and exfiltrates raw page content.

**Mitigation:**
- Extension talks only to the local Python runtime on loopback, not to external network endpoints.
- Ingest pipeline runs `contains_blocked_secret()` before storage.
- Egress filter runs on every outbound path.

**Verification:** Extension manifest has no `externally_connectable` hosts.

---

### T3: Local database theft

**Risk:** Attacker gains filesystem access and steals `personalayer.sqlite`.

**Mitigation:**
- Raw payloads encrypted with AES-256-GCM.
- Encryption key stored in Secure Enclave / OS keychain (not in filesystem).
- Without the key, stolen database reveals only schema and metadata.

**Verification:** `tests/test_production_hardening.py::TestEncryptedVault`

---

### T4: Cloud metadata deanonymization

**Risk:** Attacker correlates cloud consent metadata with public datasets to infer behavior.

**Mitigation:**
- Cloud stores only app IDs, scopes, and token prefixes.
- No timestamps of behavior, no feature names, no content.
- RLS policies prevent cross-user reads.

---

### T5: APNs notification interception

**Risk:** Attacker intercepts push notifications to learn user behavior.

**Mitigation:**
- Notifications are **silent background pushes** (`content-available: 1`, no alert/sound/badge).
- Payload contains only routing metadata (route_id, type), never behavioral text.
- APNs uses TLS 1.3 end-to-end.

**Verification:** `supabase/functions/apns-router/index.ts` enforces `alert?: never`.

---

### T6: OAuth token exfiltration

**Risk:** Attacker steals OAuth tokens from local storage.

**Mitigation:**
- Tokens stored in OS keychain / Secure Enclave, not SQLite.
- Token refresh happens locally; refresh tokens never leave the device.
- Expired tokens are auto-deleted.

---

### T7: Consent bypass via spoofed app_id

**Risk:** Attacker spoofs a legitimate app_id to gain context access.

**Mitigation:**
- Dashboard requires strong auth for app registration.
- API key verification on every request.
- App IDs are scoped to developer accounts in cloud registry.

---

## 3. Security Checklist

- [x] AES-256-GCM for raw payload encryption
- [x] OS keychain for device key and OAuth tokens
- [x] Egress filter on all outbound paths
- [x] CORS restricted to localhost/extension origins
- [x] RLS on all cloud tables
- [x] APNs silent pushes only
- [x] Secret detection at ingest
- [x] Consent revocation immediate
- [x] Hard delete removes all local + cloud references
- [x] Deterministic embeddings as CoreML fallback

---

## 4. Incident Response

If a vulnerability is discovered:

1. Report to security@personallayer.dev
2. We acknowledge within 24 hours
3. Patch within 72 hours for critical issues
4. Notify affected users via dashboard + email
