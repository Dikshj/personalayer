-- Privacy-preserving production observability.
-- Stores operational metadata only. Do not place personal content, prompts,
-- connector bodies, notifications, tokens, or SDK payloads in attributes.

create table if not exists public.observability_events (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  source text not null,
  event_name text not null,
  severity text not null default 'info'
    check (severity in ('debug','info','warning','error')),
  route text default '',
  status_code integer,
  duration_ms integer,
  attributes jsonb not null default '{}'::jsonb,
  event_hash text not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_observability_events_user_recent
  on public.observability_events(user_id, created_at desc);

alter table public.observability_events enable row level security;

create policy observability_events_user_select on public.observability_events
  for select using (auth.uid()::text = user_id);

create policy observability_events_user_insert on public.observability_events
  for insert with check (auth.uid()::text = user_id);

comment on table public.observability_events is
  'Privacy-preserving operational telemetry. Attributes must be redacted and must not contain personal content.';
