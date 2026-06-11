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

## Persona Schema

PersonaLayer separates what the user explicitly declared from what the system inferred.

Declared preferences are user-authored and authoritative. They are stored as natural language statements, with an optional structured representation for matching against context fields. They are not confidence-scored because they are facts the user stated.

Inferred persona signals are derived from metadata and activity signals. They are confidence-scored, source-linked, and editable.

Precedence rule:

```text
declared_preferences always override conflicting persona_signals
```

When `backend/pcl/composer.py` assembles a bundle, it must suppress inferred signals that conflict with an active declared preference for the same field. Bundle metadata should mark whether each field came from a declared or inferred source.

Frontend copy should surface the distinction:

- "What you told us": declared preferences.
- "What we inferred": persona signals.

Declared preference implementation target:

- New module: `backend/pcl/declared_preferences.py`
- New table: `declared_preferences`

```text
pref_id        uuid
user_id        uuid
statement      text
category       text
structured     json
authored_ts    timestamp
source         text
active         boolean
```

Example statement:

```text
I don't take meetings before noon.
```

Example categories:

- `schedule`
- `diet`
- `professional`
- `communication_style`
- `location`
- `health`
- `financial`
- `interests`

Declared preferences are captured during `/app/onboarding`, especially goals and preferences steps, and remain editable in `/app/persona`.

## Canonical Scope Vocabulary

PersonaLayer uses a canonical scope vocabulary so apps can request interoperable scopes instead of PersonaLayer-specific field names.

Implementation target:

- New module: `backend/pcl/scope_vocab.py`

Each canonical scope has:

- stable id
- plain-language description
- internal persona fields it maps to
- aliases from existing custom scopes

Initial canonical scopes:

- `schedule`
- `diet`
- `professional`
- `location`
- `health`
- `financial`
- `communication_style`
- `interests`

Example:

```text
scope id: schedule
description: Calendar patterns, availability preferences, meeting constraints, and time-of-day working habits.
internal fields: active_context.schedule, declared_preferences.schedule, persona_signals.meeting_pattern
aliases: calendar, availability, meeting_preferences
```

The consent UI at `/app/consent/:appId` displays the canonical scope name and standard description. An HCP-compatible app built against the shared vocabulary should work with PersonaLayer without custom per-app mapping.

## Runtime Architecture

```text
Input sources
  browser extension, SDK/app events, OAuth connectors, AI tools, onboarding
        |
        v
Collection layer
  scheduled collectors, OAuth token refresh, extension bridge, SDK, native clients
        |
        v
Ingestion API
  FastAPI endpoints normalize incoming metadata and signals
        |
        v
Inbound privacy tagger
  detects secrets in payloads and tags contains_secret=true for user review
        |
        v
Local storage
  raw_events, persona_signals, feature_signals, profile, permissions, audit, sync
        |
        v
Persona + context engine
  living persona, profile, daily refresh, memory tiers, context composer
        |
        v
User consent gate
  auth -> app permission scopes -> user-defined privacy boundaries
        |
        v
Output layer
  context bundles, assistant context, dashboard, audit logs, encrypted sync payloads
```

## Trust Rules

- Users own the data.
- Apps receive only context the user explicitly authorized.
- Every app query is logged and visible.
- Disconnecting an app revokes access immediately.
- Delete is real and complete.
- Sources collect metadata and signals only. Raw content such as email bodies, document content, and code is never stored or shared.
- Inbound privacy logic tags potential secrets for user visibility; it does not make outbound decisions.
- Outbound policy is user-sovereign: no system-level filters or hardcoded blocklists run after the user consent gates. PersonaLayer enforces app identity, user-granted scopes, and explicit user privacy boundaries.

## Input Sources

PersonaLayer ingests from:

- Browser extension: domain visits, search activity, and page metadata, not page content.
- SDK and app events: feature usage signals from integrated apps.
- OAuth connectors: Gmail metadata and signals only, GitHub, Google Calendar, Google Drive, Notion, Spotify, Apple Health, and YouTube.
- AI tools: Claude, ChatGPT, Perplexity, Gemini, Grok, Cursor, IDE/terminal activity, and coding agents.
- Manual onboarding: explicit seed answers from the user during setup.

All sources are metadata/signal sources. Raw content, including email bodies, document content, and code, is never stored or shared.

## Collection Layer

Collection code lives in:

- `backend/collectors/`
- `backend/pcl/connectors.py`
- `backend/pcl/integration_jobs.py`
- `extension/`
- `sdk/`
- `native/`

Collectors run on schedule through APScheduler and connector jobs refresh OAuth tokens when needed. They produce activity signals, not raw data.

Examples:

- Browser extension -> domain/search/page activity signals.
- GitHub -> repository activity, commit frequency, and language signals.
- Gmail -> email metadata signals such as sender domain, subject tags, and thread count.
- Notion -> workspace and task metadata.
- SDK -> feature usage events.

## Ingestion API

The main backend is `backend/interfaces/http_api.py`, served by FastAPI. Production API origin:

```text
https://personalayer.onrender.com
```

Primary endpoints:

- `POST /pcl/integrations`: register an OAuth integration.
- `GET /pcl/apps`: list connected apps.
- `POST /pcl/query`: internal query endpoint.
- `GET /v1/context/bundle`: serve a scoped context bundle to an agent.
- `GET /v1/control-center/summary`: user's persona summary.
- `GET /v1/control-center/signals/search`: search across signals.
- `GET /v1/user/privacy-profile`: user's current consent and rules configuration.
- `POST /v1/sync/*`: device sync endpoints.
- `POST /v1/auth/local/session`: local session auth.

At ingestion, `privacy.py` is an inbound tagger. It detects secrets such as API keys, tokens, and passwords in raw event payloads, tags them with `contains_secret: true`, and surfaces them in the privacy dashboard. It does not block storage or later sharing by itself.

## Storage Layer

Local SQLite, implemented in `backend/database.py`, stores all personal data on device:

- `raw_events`: every incoming signal before processing.
- `persona_signals`: inferred behavioral facts about the user.
- `feature_signals`: per-app usage patterns.
- `user_profiles`: stable identity layer such as name, location, skills, occupation, and projects.
- `pcl_integrations`: connected sources, auth state, and last sync.
- `pcl_apps`: registered third-party apps.
- `app_permissions`: per-app consent, granted scopes, denied scopes, consent timestamp, and query count.
- `declared_preferences`: authoritative user-authored natural language preferences plus structured matching metadata.
- `privacy_boundaries`: user-defined field-level rules. Empty by default.
- `context_bundles`: assembled bundles served to agents. Ephemeral and TTL-based.
- `query_logs`: full audit trail of every read by every app.
- `sync_devices`: trusted, pending, and revoked device registry.
- `sync_conflicts`: conflict records from cross-device sync.
- `sync_audit_logs`: every sync transfer event.

Supabase thin cloud stores developer metadata only, never raw personal history:

- `developers`
- `apps`
- `api_keys`
- `app_permissions` registration records
- `push_tokens`
- `notification_routes`
- encrypted summary blobs, using AES-GCM with keys that never leave the device

## Persona + Context Engine

The core intelligence layer turns raw signals into a structured, living persona:

- `backend/living_persona.py`: builds and updates persona signals and profile summaries from raw events.
- `backend/pcl/declared_preferences.py`: stores and resolves authoritative user-authored preferences.
- `backend/pcl/contextlayer.py`: assembles active context bundles scoped to requesting apps.
- `backend/pcl/profile.py`: manages the stable user profile.
- `backend/pcl/daily_refresh.py`: runs nightly to produce an insight digest and update signal confidence scores.
- `backend/pcl/memory.py`: tiered memory: HOT is always in the bundle, WARM is retrieved by relevance, COLD is archived.
- `backend/pcl/composer.py`: composes final bundle payloads from resolved signals and memory tiers.
- `backend/pcl/scope_vocab.py`: maps app-requested scopes to the canonical PersonaLayer scope vocabulary.

Engine outputs:

- Persona signals.
- Feature usage patterns.
- Profile summaries.
- Active context bundles.
- Memory summaries.
- Daily insight digest.
- Decision bundles.
- Bundle provenance metadata that identifies declared versus inferred fields.

## User Consent Gate

There are no system-level filters or hardcoded outbound blocklists after bundle assembly. PersonaLayer enforces only what the user explicitly configured. Three gates run in sequence on every outbound request.

Gate 1: `auth.py`, identity only:

- Is this app registered?
- Is the API key valid?
- Is the session valid?
- If no, return `403` and deny the request entirely.

Gate 2: `app_permissions`, user-granted scopes:

- Resolve scopes the user granted to the app.
- Normalize requested scopes through the canonical vocabulary in `scope_vocab.py`.
- Strip requested fields that are outside granted scopes.
- The app receives only what the user said yes to.
- PersonaLayer does not impose a system opinion on what scopes are appropriate.

Gate 2 also enforces purpose binding. Every scope grant carries a stated purpose:

```text
purpose        text
purpose_bound  boolean
```

If `purpose_bound` is true, a grant approved for one purpose cannot silently serve a bundle for another purpose. For example, a `schedule` grant approved "for restaurant booking" cannot be reused for a different stated purpose unless the user approved that purpose.

The consent flow at `/app/consent/:appId` requires each requesting app to state a purpose per scope. The user sees both the canonical scope and the stated purpose before approval.

Gate 3: `privacy_boundaries`, user-defined rules only:

- `privacy_boundaries` starts empty at install.
- It contains only rules the user explicitly created.
- Rule types are `block`, where a field is excluded from the bundle, and `redact`, where the field stays present but its value is masked.
- There are no system defaults and no pre-populated rules.

If a request passes all three gates, the bundle ships as assembled. No further interception runs.

## Output Layer

PersonaLayer outputs scoped context, not raw history:

- Context bundles: scoped JSON payloads assembled per app per request, served via `GET /v1/context/bundle`. Bundles are TTL-based and ephemeral.
- Assistant context: natural language context blocks injected into AI assistant system prompts through MCP so Claude, Cursor, Perplexity, and related tools can understand current projects, stack, preferences, and working context.
- User dashboard: `https://mypersonalayer.com`.
- Dashboard routes: `/app/persona`, `/app/apps`, `/app/privacy`, `/app/devices`, `/app/activity`, and `/app/settings`.
- Audit logs: every query is logged to `query_logs` with app, timestamp, scopes requested, scopes served, fields blocked by user rules, and result status.
- Purpose-aware audit logs: `query_logs` records the stated purpose for each read, plus whether the served bundle matched a purpose-bound grant.
- Encrypted sync payloads: delta transfers to trusted devices.

## Device Sync

Cross-device sync flow:

```text
Device A initiates pairing
  -> QR code or manual pairing code generated
Device B approves
  -> X25519 key exchange establishes shared secret
AES-GCM encrypted summary transfer
  -> receiving device claims and imports
Trusted device record stored in sync_devices
  -> every transfer logged in sync_audit_logs
```

Device states:

- `trusted`
- `pending`
- `revoked`

Conflict resolution is latest-write-wins with the conflict logged. Revocation is immediate: revoked devices cannot receive further sync.

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
- `backend/pcl/privacy.py`: local secret-blocking plus egress filtering primitives.
- `backend/pcl/composer.py`: response composer that ranks features and returns a decision-ready bundle.
- `backend/pcl/permissions.py`: app permission resolution for allowed context layers.
- `backend/pcl/onboarding.py`: five-question cold-start seed flow.
- `POST /pcl/onboarding/seed`: seed a profile before passive data exists.
- `GET /pcl/profile`: inspect the current five-layer profile projection.
- `GET /pcl/feature-usage`: inspect app-emitted feature usage signals.
- `GET /pcl/onboarding/seed`: inspect the saved cold-start seed.
- `GET /pcl/integrations/catalog`: list first-party integrations available for connection.
- `GET /pcl/integrations/catalog`: includes each connector's auth type and a raw-content-free metadata example for local import testing.
- `GET /pcl/integrations`: inspect account hint, auth status, connection state, cursor state, and sync status.
- `POST /pcl/integrations/{source}/connect`: mark a first-party integration connected with an account hint, auth status, optional expiry, and sanitized local metadata.
- `POST /pcl/integrations/{source}/oauth/start`: create an OAuth state and return a provider authorization URL when the relevant `*_OAUTH_CLIENT_ID` env var is configured. Without a client id, it returns the missing env var and state for local setup.
- `POST /pcl/integrations/oauth/callback`: consume a pending OAuth state, write a local encrypted token envelope, and mark the integration `oauth_connected_local_token_store`.
- `GET /pcl/integrations/oauth/tokens` and `DELETE /pcl/integrations/{source}/oauth/token`: inspect or revoke masked local OAuth token metadata. These routes never return raw access or refresh tokens.
- `POST /pcl/integrations/{source}/disconnect`: revoke integration connection.
- `DELETE /pcl/integrations/{source}/data`: delete integration state and imported records from that source.
- `POST /pcl/integrations/{source}/sync`: run import/sync jobs. GitHub uses the existing public activity collector when a username is configured. Gmail, Calendar, Notion, Spotify, YouTube, and Apple Health can contribute sensitive local payloads for full-persona synthesis, while credentials/secrets remain blocked at ingest and outbound bundles are filtered at egress. Connector jobs also normalize metadata into v1 `ContextEvent`s with `source: "connector"` so the raw event window, feature signals, refresh pipeline, and bundle composer see connector-derived behavior.
- `POST /pcl/apps`: register an app and its allowed context layers.
- `DELETE /pcl/apps/{app_id}/data`: delete an app registration, feature events, and query logs.
- `POST /pcl/events/feature`: ingest app-emitted feature usage as capability signals.
- `POST /pcl/query`: return a scoped decision bundle for a registered app.
- `GET /pcl/query-log`: user-visible audit log for app queries.
- `DELETE /pcl/query-log`: clear query audit logs.
- `DELETE /pcl/users/{user_id}/data`: delete user-scoped PCL seed, feature events, and query logs.
- `POST /v1/context/cold-start`: generate low-confidence synthetic episodic signals for a new app/user before real behavioral history exists.
- Accepted v1 ContextLayer events now also write a local knowledge graph reference model: `kg_nodes` for app/feature entities, `kg_edges` for app-feature relations, and `temporal_chains` for ordered accesses with a context hash. This mirrors the v4 Swift/GRDB target schema in the Python prototype without sending graph data to cloud services.
- Graph nodes store 384-dimensional embedding BLOBs in the Python reference runtime. The current embedding is deterministic local hash embedding for tests and entity-resolution plumbing; the production Swift target should replace it with on-device all-MiniLM-L6-v2 through Core ML.
- `GET /v1/context/shared-bundle`: local prototype read path for the Step 9 encrypted shared context file. This is served by the Python local runtime on `127.0.0.1:7823`.
- `/v1/web/permissions`: local web-domain grant, check, list, and revoke endpoints. The extension bridge uses these to block web bundle/track calls until a domain has explicit local permission.
- Localhost CORS is dynamic: extension origins and localhost dashboard origins are allowed, while ordinary website origins receive CORS headers only when their domain has an active local web permission grant.
- `/v1/devices/push-token`: local reference for device APNs token registration, listing, and revoke.
- `GET /v1/notifications/routes`: local reference for queued notification routes. Routes carry device routing metadata and `payload_kind`; they do not store the daily insight sentence or any behavioral text.
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
- `sdk/javascript/personal-context-layer.js`: JavaScript SDK for web or Node apps with runtime query, cleanup, web-domain permission, masked OAuth-token inspection, local push-token, and notification-route helpers.
- Web bridge exports in `sdk/javascript/personal-context-layer.js`: `isAvailable()`, `getBundle()`, and `track()` use the extension marker plus `window.postMessage`; missing extension returns `null` by default. Trusted local development shells can explicitly pass `allowLocalhostFallback: true` to use the Python local runtime without introducing any cloud fallback.
- `PersonalContextLayer.getSharedBundle()`: local prototype helper for `/v1/context/shared-bundle`; production web pages should use the extension bridge instead.
- `sdk/javascript/examples/feature-ranking-demo.html`: browser demo that ranks and dims UI features from a PCL decision bundle.
- `dashboard/index.html`: user-facing inspection surface for profile, apps, integrations, masked OAuth token records, feature usage, onboarding, query logs, consent, local web-domain bridge permissions, registered push devices, and queued notification routes.
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

Feature events are behavioral signals. Their metadata is stored locally in the encrypted raw vault for persona synthesis. Raw payloads are never exposed in agent-facing bundles.

## Ingest and Egress Boundaries

- **Ingest gate**: blocks credentials, secrets, auth tokens, cookies, passwords, private keys, and payment card-like values.
- **Local raw vault**: AES-256-GCM encrypted at rest, key stored in OS keychain / Secure Enclave.
- **Egress filter**: runs on every outbound path (MCP, API, SDK, extension, assistant, proxy, cloud, notifications). Scrubs PII, credentials, and raw content before serialization.
- **Thin cloud**: stores only developer registry, consent metadata, and push routing. No behavioral data.

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

The local prototype now models the daily refresh pipeline at `/v1/jobs/daily-refresh`. Production should schedule one isolated job per active user at 3:00 AM in the user's local timezone. The local scheduler has only one ContextLayer processing job, `contextlayer_daily_refresh`, on a 3:00 AM cron; older interval synthesis/reflection jobs are not scheduled. The local implementation stores resumable job state in `daily_refresh_jobs` and step audit rows in `daily_refresh_step_logs`.

Pipeline steps:

1. Connector sync
2. Privacy filter verification
3. Signal classifier routing
4. Profile synthesizer using the STEP-BACK PROFILING prompt
5. Inside Out decay engine
6. Bi-Mem inductive promotion
7. Bi-Mem reflective demotion
8. Tier maintenance for local graph nodes
9. Write shared context file for local SDK reads
10. Daily insight generation
11. Raw event and temporal-chain cleanup beyond 7 days

Resume behavior: pass an existing `job_id` and `step_completed`; completed steps are skipped and the job continues from the next step. `POST /v1/jobs/daily-refresh/due` evaluates each stored profile in its own timezone and runs only users past 3:00 AM local time who have not refreshed today. `GET /v1/jobs/daily-refresh` returns job history, and `GET /v1/context/brief` serves the regenerated context brief plus daily insight. Context bundles include `stale: true` if the user's `last_synthesized_at` is missing or more than 26 hours old; stale bundles also record an urgent synthesis job id.

Step 1 now calls connected first-party integration sync jobs for that user. Connector outputs are behavioral events only, for example Gmail `label-work`, Calendar `long-meeting`, Notion `tag-roadmap`, Spotify `long-focus-session`, YouTube `category-ai-tutorial`, and Apple Health `active-day`. Each connector stores an incremental `sync_cursor.last_timestamp_ms` so repeated local syncs skip already-imported metadata instead of duplicating feed items, persona signals, or v1 feature signals.

Step 8 now maintains local graph memory tiers. HOT nodes older than 48 hours move to WARM. WARM and COOL nodes decay with tier-specific rates, move downward when stale or weak, and COOL/COLD nodes can reactivate to WARM when current HOT labels provide a strong context cue. Step 9 writes `~/.personalayer/shared/bundle_{userId}.json` as an encrypted local reference bundle containing feature signals, WARM/HOT graph nodes, active context, and abstract attributes without raw events or temporal chains. The Python prototype uses a local reference encryption envelope; the Swift/App Group target should use AES-256 with the device key. Step 10 writes the daily insight locally and queues silent notification routes for active devices; the route payload does not include the insight text, so APNs/cloud routing never receives behavioral-derived content. Step 11 deletes `temporal_chains` older than 7 days while preserving synthesized graph nodes.

## Developer Auth And Consent

Local dashboard mode still works without credentials. Developer mode is activated when `Authorization: Bearer cl_*` is present.

The local prototype verifies the developer API key against `api_keys`, checks that the key belongs to the requested `app_id`, resolves the user from `x-user-token` when it uses the local `user:{id}` shape, then requires an active `app_permissions` row with every requested scope. Missing consent returns `missing_user_consent`; missing scopes return `scope_not_granted`. The Human API proxy uses `x-contextlayer-api-key` for this ContextLayer auth so `Authorization` can remain the upstream model-provider key.

The MCP v1 tools use the same authorization path. Because MCP tool calls do not carry HTTP headers in this local server, pass `developer_api_key` and `user_token` in the tool arguments for `getContextBundle`, `getFeatureSignals`, `getActiveContext`, and `getConstraints`. Omitting `developer_api_key` keeps local dashboard-style behavior.

## Thin Cloud Schema

`supabase/migrations/001_thin_cloud_registry.sql` defines the production cloud boundary: `developers`, `apps`, `api_keys`, `app_permissions`, `push_tokens`, and `notification_routes`, with RLS enabled. The migration intentionally excludes local memory tables such as raw events, temporal chains, graph nodes, feature signals, embeddings, context bundles, and synthesized attributes.

## Research Implementation Map

- FileGram: `ContextEvent` ingestion keeps a normalized behavioral spine while preserving the original payload in the local raw vault for persona synthesis. Unknown top-level fields and sensitive content are allowed locally unless they look like credentials, secrets, auth tokens, passwords, cookies, private keys, or payment card values. Agent-facing bundles never include raw payloads.
- SensorPersona: daily refresh plus stale bundle flag after 26 hours.
- MemMachine: `feature_signals.tier` with core promotion gated by usage, recency, and 5 distinct sessions.
- Bi-Mem: separate inductive and reflective refresh steps.
- Inside Out: λ decay, core `0.02`, episodic `0.12`, archive/delete thresholds.
- STEP-BACK PROFILING: Step 4 synthesizer prompt and structured abstract attributes.
- Four-tier memory reference model: local graph nodes carry `hot`, `warm`, `cool`, and `cold` tiers, decay score, access count, and compression state. The Python prototype implements tier movement and cue-based reactivation as a reference for the Swift/GRDB target.
- Semantic deduplication reference: graph node creation embeds labels locally and reuses an existing same-type node when cosine similarity is at least `0.92`. `subject_category` metadata creates concept nodes and `relates_to` edges, so connector signals like `design system` and `design systems` resolve to one concept node.
- HingeMem: per-request `resolve_intent_boundary`, never cached.
- Contextual Bandits: `/v1/context/feedback` reward/penalty updates.
- Asking Clarifying Questions: five-question onboarding seed.
- Context Steering: `/v1/chat/completions` injects context at inference time.
- Extension bridge only for web: content script injects `data-cl-ext="1"`, handles `CL_GET_BUNDLE` and `CL_TRACK`, and returns `CL_BUNDLE_RESPONSE` / `CL_TRACK_RESPONSE` through `window.postMessage`. The background worker checks local `web_domain_permissions` before serving a bundle or writing a track event.
- Synthetic Interaction Data: `/v1/context/cold-start` creates low-confidence `is_synthetic` episodic signals from role/domain/app priors. Real usage clears the synthetic flag and overwrites these rapidly; full LLM generation remains a production TODO.
- App consent and developer access: local `developers`, `apps`, `api_keys`, and `app_permissions` tables model the Supabase production schema. Revoked consent blocks `/v1/context/bundle` for that user/app.

## Immediate Build Plan

1. Add provider-specific token exchange and encrypted token storage for Gmail, Calendar, and Notion.
2. Expand connector-specific backfill cursors from local metadata imports to provider OAuth delta tokens and sync windows.
3. Add cloud account and sync boundary after the local prototype behavior is solid.
