# PersonaLayer System Daemon Architecture

PersonaLayer is a local context daemon. The browser extension is one collector, not the product center.

## Runtime Shape

```text
Local daemon on 127.0.0.1:7823
  owns storage, event ingestion, signal extraction, policy, audit

Collectors
  browser extension
  shell wrappers
  IDE and coding-agent watchers
  local LLM proxy
  GitHub sync
  future app connectors

Interfaces
  HTTP API for local collectors and dashboard
  MCP server for AI tools
  CLI later

Policy
  apps negotiate context contracts
  daemon returns scoped context only
  raw data stays local
  every scoped context read is auditable
```

## Core Rule

Collectors produce activity events. They do not decide persona, permissions, or sharing.

The daemon ingests events through one path, derives local signals, stores them in SQLite, and exposes only scoped context through policy.

## Current Implementation

- `backend/core/daemon.py` is the system-level ingestion core.
- `backend/interfaces/http_api.py` is the HTTP interface over the daemon.
- `backend/interfaces/mcp_server.py` is the MCP interface.
- `backend/main.py` and `backend/mcp_server.py` are compatibility entrypoints.
- `backend/policy.py` owns context contracts and scoped persona construction.
- `backend/living_persona.py` owns local derived signals.
- `backend/collectors/base.py` defines collector specs, permissions, and event types.
- `backend/collectors/registry.py` registers collector classes, startup hooks, and scheduled collector jobs.
- `backend/storage/migrations.py` owns durable SQLite schema migrations.
- `backend/settings.py` controls collector enablement from environment variables or `~/.personalayer/settings.json`.
- `backend/scheduler.py` schedules registered collector jobs and persona refresh/extraction jobs.
- `scripts/install_windows_startup.ps1` registers the daemon at Windows login.

## Local Endpoints

- `GET /daemon/status`: daemon capabilities and collector list.
- `POST /event`: browser activity collector compatibility endpoint.
- `POST /feed-event`: generic activity feed for shell, IDE, LLM, and social collectors.
- `POST /context/negotiate`: create a scoped sharing contract.
- `GET /context/{contract_id}`: return only the context allowed by that contract.
- `POST /context/{contract_id}/revoke`: revoke future access.

## Next Architecture Steps

1. Add tests for migration idempotency.
2. Expose collector enable/disable state through `/daemon/status`.
3. Add HTTP endpoints to update collector settings without editing JSON by hand.
4. Add a small tray app or service monitor for daemon health.

## Collector Settings

Collectors can be enabled with either environment variables or a local settings file.

Environment:

```text
PERSONALAYER_ENABLED_COLLECTORS=claude_code,github
PERSONALAYER_DISABLED_COLLECTORS=claude_code
```

Settings file:

```json
{
  "collectors": {
    "github": {"enabled": true},
    "claude_code": {"enabled": false}
  }
}
```
