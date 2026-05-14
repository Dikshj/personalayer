-- ContextLayer thin cloud schema.
-- This migration is intentionally limited to account, developer registry,
-- consent metadata, and APNs routing metadata. Do not add behavioral tables here.

create extension if not exists pgcrypto;

create table if not exists public.developers (
  id uuid primary key default gen_random_uuid(),
  auth_user_id uuid references auth.users(id) on delete cascade,
  email text not null unique,
  name text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.apps (
  id uuid primary key default gen_random_uuid(),
  developer_id uuid not null references public.developers(id) on delete cascade,
  app_id text not null unique,
  name text not null,
  domain text not null default '',
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.api_keys (
  id uuid primary key default gen_random_uuid(),
  developer_id uuid not null references public.developers(id) on delete cascade,
  app_id text not null default '',
  key_hash text not null unique,
  key_prefix text not null,
  env text not null default 'test' check (env in ('test', 'live')),
  is_active boolean not null default true,
  last_used_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.app_permissions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  app_id text not null references public.apps(app_id) on delete cascade,
  developer_id uuid references public.developers(id) on delete set null,
  scopes text[] not null default array['getFeatureUsage']::text[],
  granted_via text not null default 'explicit',
  is_active boolean not null default true,
  granted_at timestamptz not null default now(),
  revoked_at timestamptz,
  unique (user_id, app_id)
);

create table if not exists public.push_tokens (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  device_id text not null,
  apns_token text not null,
  platform text not null default 'ios' check (platform in ('ios', 'macos')),
  environment text not null default 'development' check (environment in ('development', 'production')),
  is_active boolean not null default true,
  registered_at timestamptz not null default now(),
  revoked_at timestamptz,
  unique (user_id, device_id)
);

create table if not exists public.notification_routes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  device_id text not null,
  push_token_id uuid not null references public.push_tokens(id) on delete cascade,
  notification_type text not null,
  deliver_after timestamptz not null,
  payload_kind text not null default 'silent_local_insight',
  status text not null default 'queued' check (status in ('queued', 'sent', 'failed', 'cancelled')),
  created_at timestamptz not null default now()
);

create index if not exists idx_apps_developer_id on public.apps(developer_id);
create index if not exists idx_api_keys_developer_id on public.api_keys(developer_id);
create index if not exists idx_app_permissions_user_id on public.app_permissions(user_id);
create index if not exists idx_push_tokens_user_id on public.push_tokens(user_id);
create index if not exists idx_notification_routes_user_id on public.notification_routes(user_id);

alter table public.developers enable row level security;
alter table public.apps enable row level security;
alter table public.api_keys enable row level security;
alter table public.app_permissions enable row level security;
alter table public.push_tokens enable row level security;
alter table public.notification_routes enable row level security;

create policy developers_owner_select on public.developers
  for select using (auth.uid() = auth_user_id);
create policy developers_owner_insert on public.developers
  for insert with check (auth.uid() = auth_user_id);
create policy developers_owner_update on public.developers
  for update using (auth.uid() = auth_user_id) with check (auth.uid() = auth_user_id);

create policy apps_developer_owner_all on public.apps
  for all using (
    exists (
      select 1 from public.developers d
      where d.id = apps.developer_id and d.auth_user_id = auth.uid()
    )
  ) with check (
    exists (
      select 1 from public.developers d
      where d.id = apps.developer_id and d.auth_user_id = auth.uid()
    )
  );

create policy api_keys_developer_owner_all on public.api_keys
  for all using (
    exists (
      select 1 from public.developers d
      where d.id = api_keys.developer_id and d.auth_user_id = auth.uid()
    )
  ) with check (
    exists (
      select 1 from public.developers d
      where d.id = api_keys.developer_id and d.auth_user_id = auth.uid()
    )
  );

create policy app_permissions_user_select on public.app_permissions
  for select using (auth.uid() = user_id);
create policy app_permissions_user_insert on public.app_permissions
  for insert with check (auth.uid() = user_id);
create policy app_permissions_user_update on public.app_permissions
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy push_tokens_user_all on public.push_tokens
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy notification_routes_user_select on public.notification_routes
  for select using (auth.uid() = user_id);

comment on schema public is
  'ContextLayer cloud stores auth, developer registry, app permission metadata, and APNs routing only.';
comment on table public.app_permissions is
  'Consent metadata only. No raw events, graph nodes, context bundles, or synthesized attributes.';
comment on table public.notification_routes is
  'APNs routing metadata only. payload_kind must not contain behavioral text or daily insight content.';
