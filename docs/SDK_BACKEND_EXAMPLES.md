# SDK And Backend Examples

These examples target the local PersonaLayer backend.

## Memory

```bash
curl -X POST "http://127.0.0.1:7823/v1/memory/init?user_id=local_user"

curl -X POST http://127.0.0.1:7823/v1/memory/projects/append \
  -H "Content-Type: application/json" \
  -d '{"user_id":"local_user","heading":"PersonaLayer","entry":"Building local-first personalization.","source":"manual"}'

curl -X POST http://127.0.0.1:7823/v1/memory/search \
  -H "Content-Type: application/json" \
  -d '{"user_id":"local_user","query":"local personalization","scopes":["projects"]}'
```

## Skills

```bash
curl -X POST http://127.0.0.1:7823/pcl/skills \
  -H "Content-Type: application/json" \
  -d '{"skill_id":"code-review","name":"Code Review","category":"engineering","memory_scopes":["work-style","projects"],"required_tools":["git","pytest"]}'

curl -X POST http://127.0.0.1:7823/pcl/skills/route \
  -H "Content-Type: application/json" \
  -d '{"user_id":"local_user","message":"review this backend change","include_memory":true}'
```

## Sync

```bash
curl -X POST http://127.0.0.1:7823/v1/sync/devices \
  -H "Content-Type: application/json" \
  -d '{"user_id":"local_user","device_id":"phone","device_name":"Phone","public_key":"placeholder-public-key"}'

curl -X POST http://127.0.0.1:7823/v1/sync/devices/phone/trust \
  -H "Content-Type: application/json" \
  -d '{"user_id":"local_user"}'

curl -X POST http://127.0.0.1:7823/v1/sync/snapshot \
  -H "Content-Type: application/json" \
  -d '{"user_id":"local_user","device_id":"laptop","device_name":"Laptop"}'
```

## Observability

```bash
curl -X POST http://127.0.0.1:7823/v1/observability/events \
  -H "Content-Type: application/json" \
  -d '{"user_id":"local_user","source":"sdk","event_name":"request_complete","attributes":{"email":"person@example.com","duration_ms":42}}'
```

The backend redacts common PII and drops secret-like fields before storing observability attributes.

## Developer Keys

```bash
curl -X POST http://127.0.0.1:7823/v1/developer/register \
  -H "Content-Type: application/json" \
  -d '{"email":"dev@example.com","name":"Dev"}'

curl -X POST http://127.0.0.1:7823/v1/developer/keys \
  -H "Content-Type: application/json" \
  -d '{"developer_id":"<developer_id>","app_id":"demo_app","env":"test"}'

curl -X POST http://127.0.0.1:7823/v1/developer/keys/<key_id>/rotate \
  -H "Content-Type: application/json" \
  -d '{"developer_id":"<developer_id>"}'
```

Raw API keys are returned only on create/rotate. List and audit endpoints expose prefixes and metadata only.
