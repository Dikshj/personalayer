-- Encrypted cross-device summary sync.
-- Stores encrypted summary blobs and version pointers only.
-- No raw events, plaintext memory, feature signals, embeddings, or graph nodes.

create table if not exists public.sync_devices (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  device_id text not null,
  device_name text default '',
  public_key text default '',
  trust_status text default 'trusted' check (trust_status in ('pending','trusted','revoked')),
  last_seen_at timestamptz,
  revoked_at timestamptz,
  created_at timestamptz default now(),
  unique(user_id, device_id)
);

create table if not exists public.encrypted_summary_blobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  device_id text not null,
  version text not null,
  parent_version text default '',
  summary_hash text not null,
  encrypted_blob jsonb not null,
  merge_status text default 'received' check (merge_status in ('local','received','merged','conflict')),
  created_at timestamptz default now(),
  unique(user_id, device_id, version)
);

create table if not exists public.sync_conflicts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  local_version text not null,
  remote_version text not null,
  reason text not null,
  status text default 'open' check (status in ('open','resolved','ignored')),
  details jsonb default '{}'::jsonb,
  created_at timestamptz default now(),
  resolved_at timestamptz
);

create index if not exists idx_sync_devices_user on public.sync_devices(user_id);
create index if not exists idx_summary_blobs_user_device on public.encrypted_summary_blobs(user_id, device_id, created_at desc);
create index if not exists idx_sync_conflicts_user_status on public.sync_conflicts(user_id, status, created_at desc);

alter table public.sync_devices enable row level security;
alter table public.encrypted_summary_blobs enable row level security;
alter table public.sync_conflicts enable row level security;

create policy sync_devices_owner_all on public.sync_devices
  for all using (user_id = auth.uid())
  with check (user_id = auth.uid());

create policy encrypted_summary_blobs_owner_all on public.encrypted_summary_blobs
  for all using (user_id = auth.uid())
  with check (user_id = auth.uid());

create policy sync_conflicts_owner_all on public.sync_conflicts
  for all using (user_id = auth.uid())
  with check (user_id = auth.uid());
