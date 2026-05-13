# Personal Context Layer Product Architecture

Working name: TBD. The product is a Personal Context Layer (PCL): an account-backed service that builds a living model of a user and exposes scoped, typed context to application agents at runtime.

## Product Definition

PCL is personalization infrastructure. Users sign up once, connect accounts, and control their data. Developers integrate an SDK and MCP/query API so their agents can ask what UI, workflows, and features are relevant for this user right now.

The product promise is: apps stop showing every feature to every user. They query PCL and receive a decision-ready bundle: ranked features, relevant context, and constraints.

## Audiences

User product:

- Conversational interface over the user's own context layer.
- Connected accounts such as Gmail, Calendar, Notion, GitHub, and browser/import sources.
- Living profile the user can inspect and correct.
- Privacy controls, per-app permissions, disconnect/delete flows.
- Activity digest showing every app query and what fields were returned.

Developer platform:

- SDK for emitting behavioral signals.
- MCP server and query API for runtime context.
- Documentation, local dev tools, test users, and app directory.
- Query logs and permission scopes surfaced to users.

## Five Context Layers

1. Identity and role: who the user is, domain, skill level, current project.
2. Capability signals: features used, frequency, recency decay, confidence.
3. Behavior patterns: time of day, session length, workflow style.
4. Active context: current project, active tools, current goal, blockers.
5. Explicit preferences: hard user rules, disabled features, declared preferences.

## Runtime Architecture

```text
Connected apps and first-party integrations
  emit behavioral signals through SDK/API
        |
        v
Privacy filter
  strips PII and raw content before storage
        |
        v
Signal store and profile builder
  account-backed, local-first with cloud sync later
        |
        v
Policy and permission layer
  per-app scopes, revocation, audit log
        |
        v
Response composer
  ranks features and returns typed decision bundle
        |
        v
MCP server / query API
  getProfile, getFeatureUsage, getContext, getConstraints
```

## Trust Rules

- Users own the data.
- Apps never receive raw data or a durable copy.
- Every app query is logged and visible.
- Disconnecting an app revokes access immediately.
- Delete is real and complete.
- Privacy filtering happens before storage, not after.

Current delete controls:

- `DELETE /pcl/users/{user_id}/data` removes that user's onboarding seed, feature events, and PCL query logs.
- `DELETE /pcl/apps/{app_id}/data` removes the app registration plus its feature events and query logs.
- `DELETE /pcl/integrations/{source}/data` removes the integration record plus imported feed items and persona signals for that source.
- `DELETE /pcl/query-log` clears app query audit logs, optionally scoped by `app_id` or `user_id`.

## Cold Start

1. Five-question natural language onboarding seeds the initial profile.
2. Connected-account import creates passive behavioral signals.
3. First-party integrations provide immediate value before third-party developers arrive.

Current implementation:

- `GET /pcl/onboarding/questions` returns the five seed questions.
- `POST /pcl/onboarding/seed` stores scrubbed answers and a generated five-layer profile seed.
- `/pcl/query` merges onboarding seeds with living local signals so brand-new users receive useful personalization immediately.

## Current Repo Mapping

- `backend/pcl/models.py`: typed five-layer context and decision bundle schemas.
- `backend/pcl/privacy.py`: pre-store PII and raw-content filtering primitives.
- `backend/pcl/composer.py`: response composer that ranks features and returns a decision-ready bundle.
- `backend/pcl/permissions.py`: app permission resolution for allowed context layers.
- `backend/pcl/onboarding.py`: five-question cold-start seed flow.
- `POST /pcl/onboarding/seed`: seed a profile before passive data exists.
- `GET /pcl/profile`: inspect the current five-layer profile projection.
- `GET /pcl/feature-usage`: inspect app-emitted feature usage signals.
- `GET /pcl/onboarding/seed`: inspect the saved cold-start seed.
- `GET /pcl/integrations/catalog`: list first-party integrations available for connection.
- `GET /pcl/integrations`: inspect connection and sync status.
- `POST /pcl/integrations/{source}/connect`: mark a first-party integration connected.
- `POST /pcl/integrations/{source}/disconnect`: revoke integration connection.
- `DELETE /pcl/integrations/{source}/data`: delete integration state and imported records from that source.
- `POST /pcl/integrations/{source}/sync`: run import/sync jobs. GitHub uses the existing public activity collector when a username is configured. Gmail, Calendar, Notion, Spotify, YouTube, and Apple Health import metadata payloads from the connected integration record and emit sanitized feed items/persona signals without storing raw message, event, page, transcript, track, or health-note content. Connector jobs also normalize metadata into strict v1 `ContextEvent`s with `source: "connector"` so the same privacy filter, raw event window, feature signals, refresh pipeline, and bundle composer see connector-derived behavior.
- `POST /pcl/apps`: register an app and its allowed context layers.
- `DELETE /pcl/apps/{app_id}/data`: delete an app registration, feature events, and query logs.
- `POST /pcl/events/feature`: ingest app-emitted feature usage as capability signals.
- `POST /pcl/query`: return a scoped decision bundle for a registered app.
- `GET /pcl/query-log`: user-visible audit log for app queries.
- `DELETE /pcl/query-log`: clear query audit logs.
- `DELETE /pcl/users/{user_id}/data`: delete user-scoped PCL seed, feature events, and query logs.
- `POST /v1/context/cold-start`: generate low-confidence synthetic episodic signals for a new app/user before real behavioral history exists.
- `GET /v1/context/privacy-drops`: return privacy-filter rejection logs for user-visible audit.
- `POST /v1/context/raw-events/cleanup`: delete raw events older than a requested retention window, normally 7 days.
- `POST /v1/auth/consent`: record user consent for an app and its granted scopes.
- `GET /v1/auth/consent`: list a user's app permissions.
- `DELETE /v1/auth/consent/{app_id}`: revoke an app's access for the user.
- `POST /v1/developer/register`: create or update a local developer record.
- `POST /v1/developer/apps`: register an app under a developer.
- `GET /v1/developer/keys`: list API keys without exposing raw key material.
- `POST /v1/developer/keys`: create a local developer API key; raw key is shown once.
- `POST /v1/chat/completions`: OpenAI-compatible local ContextLayer proxy. If any message includes `{cl_context}`, the proxy resolves a live context bundle, injects a system context prefix, strips the token from the user message, and forwards to the upstream OpenAI-compatible API when an upstream key is configured. Without an upstream key, it returns a dry-run payload for local verification.
- `POST /v1/assistant/chat`: user-facing personal context assistant. It builds a full bundle for the user, constructs a system prompt from identity, abstract profile, top features, behavior, active context, and preferences, and answers through the configured upstream LLM. Without an upstream key, it returns a dry-run synthesized summary plus the exact payload.
- `sdk/python/personal_context_layer.py`: developer SDK for app registration, feature tracking, personalization queries, revoke, and delete flows.
- `sdk/javascript/personal-context-layer.js`: JavaScript SDK for web or Node apps with runtime query and cleanup helpers.
- `sdk/javascript/examples/feature-ranking-demo.html`: browser demo that ranks and dims UI features from a PCL decision bundle.
- `dashboard/index.html`: user-facing inspection surface for profile, apps, integrations, feature usage, onboarding, and query logs.
- MCP tools in `backend/interfaces/mcp_server.py`: legacy persona tools plus `getProfile`, `getFeatureUsage`, `getContext`, `getContextBundle`, `getFeatureSignals`, `getActiveContext`, and `getConstraints`.
- Existing local daemon remains the prototype runtime for ingestion, policy, MCP, and dashboard flows.

## Developer API Shape

Register an app:

```json
{
  "app_id": "mail_app",
  "name": "Mail App",
  "allowed_layers": ["identity_role", "active_context"]
}
```

Query the layer:

```json
{
  "app_id": "mail_app",
  "user_id": "user_1",
  "requested_layers": ["identity_role", "capability_signals"],
  "features": [
    {"feature_id": "smart_reply", "name": "Smart Reply"},
    {"feature_id": "newsletter_filter", "name": "Newsletter Filter"}
  ]
}
```

The response only includes layers allowed for that app. Denied and revoked-app queries are logged too.

Emit feature usage:

```json
{
  "app_id": "mail_app",
  "user_id": "user_1",
  "feature_id": "smart_reply",
  "feature_name": "Smart Reply",
  "event_type": "used",
  "weight": 1.0,
  "timestamp": 1740000000000
}
```

Feature events are behavioral signals only. Metadata and raw content are dropped before storage.

MCP tool mirror:

- `getProfile`: returns the typed user context profile.
- `getFeatureUsage`: returns older `/pcl` aggregated feature usage signals.
- `getContext`: returns the older scoped decision bundle for a registered app and logs the query.
- `getContextBundle`: returns the v1 intent-bounded ContextLayer bundle.
- `getFeatureSignals`: returns v1 feature signal rows with tier, recency, and synthetic status.
- `getActiveContext`: returns the current active context heartbeat.
- `getConstraints`: returns hard explicit preferences.

## Local Context Steering Proxy

The local prototype exposes the Human API proxy shape at `/v1/chat/completions`.

Example request:

```json
{
  "model": "gpt-4.1-mini",
  "user_id": "local_user",
  "app_id": "mail_app",
  "messages": [
    {"role": "user", "content": "{cl_context} Draft a concise reply."}
  ]
}
```

The proxy injects:

```text
[ContextLayer user profile]
features_used: smart-reply, inbox-zero
style: compact
timing: afternoon
current_project: Inbox cleanup
constraints: {}
abstract:
[End context]
```

Set `OPENAI_API_KEY` or pass the upstream model key as `Authorization: Bearer ...` to forward upstream. Leave it unset to receive a dry-run response showing the exact steered payload. For ContextLayer developer authorization, pass `x-contextlayer-api-key: cl_*` and `x-user-token: user:{id}`; the proxy then requires active consent with the `context_steering` scope before injecting context. If `Authorization` itself contains a `cl_*` key, the local prototype treats it as a ContextLayer key instead of an upstream model key.

## Personal Assistant

The local user-facing assistant is available at `/v1/assistant/chat`.

Example request:

```json
{
  "user_id": "local_user",
  "message": "What have I been working on and what should I focus on today?"
}
```

The assistant builds a full ContextLayer bundle and prompt from synthesized profile data. It does not expose raw event rows in the answer. Set `OPENAI_API_KEY` or pass `Authorization: Bearer ...` to call an upstream model; otherwise the endpoint returns a dry-run response for local testing.

## Daily Refresh Architecture

The local prototype now models the daily refresh pipeline at `/v1/jobs/daily-refresh`. Production should schedule one isolated job per active user at 3:00 AM in the user's local timezone. The local implementation stores resumable job state in `daily_refresh_jobs` and step audit rows in `daily_refresh_step_logs`.

Pipeline steps:

1. Connector sync
2. Privacy filter verification
3. Signal classifier routing
4. Profile synthesizer using the STEP-BACK PROFILING prompt
5. Inside Out decay engine
6. Bi-Mem inductive promotion
7. Bi-Mem reflective demotion
8. TSUBASA monthly long-horizon distillation
9. Brief regeneration for "Copy my context"
10. Daily insight generation
11. Raw event cleanup beyond 7 days

Resume behavior: pass an existing `job_id` and `step_completed`; completed steps are skipped and the job continues from the next step. `POST /v1/jobs/daily-refresh/due` evaluates each stored profile in its own timezone and runs only users past 3:00 AM local time who have not refreshed today. `GET /v1/jobs/daily-refresh` returns job history, and `GET /v1/context/brief` serves the regenerated context brief plus daily insight. Context bundles include `stale: true` if the user's `last_synthesized_at` is missing or more than 26 hours old; stale bundles also record an urgent synthesis job id.

Step 1 now calls connected first-party integration sync jobs for that user. Connector outputs are behavioral events only, for example Gmail `label-work`, Calendar `long-meeting`, Notion `tag-roadmap`, Spotify `long-focus-session`, YouTube `category-ai-tutorial`, and Apple Health `active-day`.

## Developer Auth And Consent

Local dashboard mode still works without credentials. Developer mode is activated when `Authorization: Bearer cl_*` is present.

The local prototype verifies the developer API key against `api_keys`, checks that the key belongs to the requested `app_id`, resolves the user from `x-user-token` when it uses the local `user:{id}` shape, then requires an active `app_permissions` row with every requested scope. Missing consent returns `missing_user_consent`; missing scopes return `scope_not_granted`. The Human API proxy uses `x-contextlayer-api-key` for this ContextLayer auth so `Authorization` can remain the upstream model-provider key.

The MCP v1 tools use the same authorization path. Because MCP tool calls do not carry HTTP headers in this local server, pass `developer_api_key` and `user_token` in the tool arguments for `getContextBundle`, `getFeatureSignals`, `getActiveContext`, and `getConstraints`. Omitting `developer_api_key` keeps local dashboard-style behavior.

## Research Implementation Map

- FileGram: strict `ContextEvent` ingestion and no content fields in `/v1/ingest/*`. The only accepted metadata fields are `hour_of_day`, `day_of_week`, and `subject_category`. Unknown top-level fields are preserved by the HTTP request model long enough to be rejected and logged by the privacy filter.
- SensorPersona: daily refresh plus stale bundle flag after 26 hours.
- MemMachine: `feature_signals.tier` with core promotion gated by usage, recency, and 5 distinct sessions.
- Bi-Mem: separate inductive and reflective refresh steps.
- Inside Out: λ decay, core `0.02`, episodic `0.12`, archive/delete thresholds.
- STEP-BACK PROFILING: Step 4 synthesizer prompt and structured abstract attributes.
- TSUBASA: monthly Step 8 long-horizon distillation.
- HingeMem: per-request `resolve_intent_boundary`, never cached.
- Contextual Bandits: `/v1/context/feedback` reward/penalty updates.
- Asking Clarifying Questions: five-question onboarding seed.
- Context Steering: `/v1/chat/completions` injects context at inference time.
- Synthetic Interaction Data: `/v1/context/cold-start` creates low-confidence `is_synthetic` episodic signals from role/domain/app priors. Real usage clears the synthetic flag and overwrites these rapidly; full LLM generation remains a production TODO.
- App consent and developer access: local `developers`, `apps`, `api_keys`, and `app_permissions` tables model the Supabase production schema. Revoked consent blocks `/v1/context/bundle` for that user/app.

## Immediate Build Plan

1. Add OAuth/account connection flow for cloud-backed Gmail, Calendar, and Notion imports.
2. Add connector-specific backfill cursors and incremental sync windows.
3. Add cloud account and sync boundary after the local prototype behavior is solid.
