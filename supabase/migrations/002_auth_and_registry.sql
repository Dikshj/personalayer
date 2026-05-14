-- Auth integration and developer profile bridge.
-- STRICTLY aligned with 001_thin_cloud_registry.sql schema.
-- Do NOT add columns that do not exist in 001.

-- Bridge auth.users to developers
create table if not exists public.developer_profiles (
  id uuid primary key default gen_random_uuid(),
  auth_user_id uuid not null references auth.users(id) on delete cascade,
  email text not null,
  created_at timestamptz not null default now(),
  unique (auth_user_id)
);

-- Trigger: auto-create developer_profile on auth.users insert
create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.developer_profiles (auth_user_id, email)
  values (new.id, new.email)
  on conflict (auth_user_id) do nothing;
  return new;
end;
$$ language plpgsql security definer;

-- Only create trigger if not exists
do $$
begin
  if not exists (
    select 1 from pg_trigger where tgname = 'on_auth_user_created'
  ) then
    create trigger on_auth_user_created
      after insert on auth.users
      for each row execute function public.handle_new_user();
  end if;
end $$;

-- verify_api_key: returns ONLY columns that exist in api_keys table
-- api_keys columns: id, developer_id, app_id, key_hash, key_prefix, env, is_active, last_used_at, created_at
create or replace function public.verify_api_key(api_key text)
returns table (
  key_id uuid,
  developer_id uuid,
  app_id text,
  env text,
  valid boolean
) as $$
declare
  prefix text;
  hashed text;
begin
  prefix := split_part(api_key, '.', 1);
  hashed := encode(digest(api_key, 'sha256'), 'hex');

  return query
  select
    ak.id as key_id,
    ak.developer_id,
    ak.app_id,
    ak.env,
    (ak.is_active = true) as valid
  from public.api_keys ak
  where ak.key_prefix = prefix
    and ak.key_hash = hashed
    and ak.is_active = true;
end;
$$ language plpgsql security definer;

-- touch_api_key: updates last_used_at for a given key_id
create or replace function public.touch_api_key(key_id uuid)
returns void as $$
begin
  update public.api_keys
  set last_used_at = now()
  where id = key_id;
end;
$$ language plpgsql security definer;

-- RLS for developer_profiles
alter table public.developer_profiles enable row level security;

create policy developer_profiles_owner_select on public.developer_profiles
  for select using (auth.uid() = auth_user_id);
create policy developer_profiles_owner_insert on public.developer_profiles
  for insert with check (auth.uid() = auth_user_id);
create policy developer_profiles_owner_update on public.developer_profiles
  for update using (auth.uid() = auth_user_id) with check (auth.uid() = auth_user_id);
