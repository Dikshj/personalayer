# ContextLayer Supabase Thin Cloud

This folder is for the production cloud boundary only. It must stay limited to:

- Supabase Auth users.
- Developer registry: `developers`, `apps`, `api_keys`.
- Consent metadata: `app_permissions`.
- APNs routing metadata: `push_tokens`, `notification_routes`.

Do not add raw events, temporal chains, knowledge graph nodes, context bundles, synthesized attributes, feature signals, embeddings, or integration payloads to Supabase.

## Apply Locally

```bash
cp .env.example .env
supabase start
supabase db reset
```

## Apply To A Project

```bash
supabase link --project-ref your-project-ref
supabase db push
```

Set only cloud-bound environment variables in the deployment environment:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- APNs routing variables when a push worker exists.

Do not configure any environment variable that causes behavioral ingestion or profile synthesis to run in cloud infrastructure.

## Boundary

The cloud can answer who the user is, which developer apps exist, which app has consent, and where APNs should route a silent notification. It cannot answer what the user did, what the user cares about, what the graph contains, or what the daily insight says.
