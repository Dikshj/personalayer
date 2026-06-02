# Personal Layer

**Local-first personal context layer for AI agents.**

Your apps and AI assistants should know your preferences without you explaining them repeatedly. Personal Layer observes your digital behavior, builds a private profile on your device, and shares scoped context with the apps you trust.

> **Production Status**: This codebase is transitioning from prototype to production. The Python FastAPI backend is the local reference runtime, and the iOS app is the native production target.

---

## Architecture

```
Connected apps and integrations
  |
  v
Local ingest gate (blocks credentials/secrets only)
  |
  v
Encrypted raw vault (AES-256-GCM, device key)
  |
  v
Persona synthesis (Core ML all-MiniLM-L6-v2 + STEP-BACK profiling)
  |
  v
Egress privacy filter (PII scrubbed, raw content stripped)
  |
  v
Scoped context bundles → MCP / SDK / Extension / Assistant
```

- **Raw data stays local** in an encrypted vault.
- **Thin cloud** (Supabase) stores only developer registry, consent metadata, and push routing.
- **Every outbound path** is filtered before it leaves your device.

---

## Quick Start

### Python Prototype (local dev)

```bash
cd backend
pip install -r requirements.txt
python main.py
# Dashboard: http://localhost:7823
```

### iOS App

```bash
scripts/build-ios.sh
```

---

## Privacy

- [Privacy Policy](docs/PRIVACY_POLICY.md)
- [Terms of Service](docs/TERMS_OF_SERVICE.md)
- [Threat Model](docs/THREAT_MODEL.md)

---

## Project Structure

| Path | Purpose |
|------|---------|
| `backend/` | Python FastAPI reference runtime |
| `native/ios/` | Swift app + GRDB |
| `extension/` | Chrome MV3 extension |
| `sdk/python/` | Python SDK |
| `sdk/javascript/` | JavaScript/TypeScript SDK |
| `supabase/` | Thin cloud migrations + edge functions |
| `tests/` | Production hardening tests |
| `docs/` | Architecture, privacy, threat model |

---

## Security

- AES-256-GCM encrypted local vault
- OS keychain / Secure Enclave for device key and OAuth tokens
- Egress filter on every outbound path (MCP, API, SDK, extension, cloud, notifications)
- CORS restricted to localhost + extension origins
- Row-level security on all cloud tables
- Silent APNs pushes only (no behavioral text in payload)

---

## License

MIT
