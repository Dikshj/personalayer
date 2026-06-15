# Backend API Surfaces

This is the local backend surface that can be built and tested without production credentials.

## Memory

- `POST /v1/memory/init`
- `GET /v1/memory/files`
- `GET /v1/memory/{scope}`
- `PUT /v1/memory/{scope}`
- `POST /v1/memory/{scope}/append`
- `DELETE /v1/memory/{scope}`
- `POST /v1/memory/search`
- `GET /v1/memory/diffs`
- `POST /v1/memory/diffs`
- `POST /v1/memory/diffs/{diff_id}/approve`
- `POST /v1/memory/diffs/{diff_id}/reject`
- `POST /v1/memory/diffs/{diff_id}/apply`
- `GET /v1/memory/sources`
- `PUT /v1/memory/sources/{source}`

Memory writes are local-first. Source toggles disable a source, audit logs record changes, and persona diffs auto-apply by default.

## Skills

- `POST /pcl/skills`
- `GET /pcl/skills`
- `GET /pcl/skills/{skill_id}`
- `POST /pcl/skills/{skill_id}/disable`
- `POST /pcl/skills/route`

Skills describe task-specific capabilities and can include allowed layers, memory scopes, required tools, and privacy rules.

## Cross-Device Sync

- `GET /v1/sync/state`
- `GET /v1/sync/devices`
- `POST /v1/sync/devices`
- `POST /v1/sync/devices/{device_id}/trust`
- `POST /v1/sync/devices/{device_id}/revoke`
- `POST /v1/sync/snapshot`
- `POST /v1/sync/import`
- `GET /v1/sync/conflicts`
- `POST /v1/sync/conflicts/{conflict_id}/resolve`
- `GET /v1/sync/audit`
- `POST /v1/sync/snapshots/compact`

Snapshots return encrypted summary blobs and public metadata. Conflict resolution supports `accept_remote`, `keep_local`, and `ignore`. Compaction keeps the newest snapshots per device.

## OAuth And Connectors

- `GET /pcl/integrations/catalog`
- `GET /pcl/integrations`
- `POST /pcl/integrations/{source}/connect`
- `POST /pcl/integrations/{source}/oauth/start`
- `POST /pcl/integrations/oauth/callback`
- `POST /pcl/integrations/{source}/oauth/refresh`
- `DELETE /pcl/integrations/{source}/oauth/token`
- `POST /pcl/integrations/{source}/sync`
- `POST /pcl/integrations/{source}/disconnect`
- `DELETE /pcl/integrations/{source}/data`

OAuth tokens are encrypted locally. Expired OAuth connections refresh before sync. Failed connector syncs schedule retry metadata through `next_sync_after`.

## Developer Platform

- `POST /v1/developer/register`
- `POST /v1/developer/apps`
- `GET /v1/developer/keys`
- `POST /v1/developer/keys`
- `DELETE /v1/developer/keys/{key_id}`
- `POST /v1/developer/keys/{key_id}/rotate`

API key list responses never include the raw key. Rotation revokes the old key and returns the new raw key once.

## Observability

- `GET /v1/observability/events`
- `POST /v1/observability/events`

Observability attributes are redacted before storage. Secret-like fields are dropped and common PII values are scrubbed.
