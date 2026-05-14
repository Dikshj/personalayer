-- Auth integration and developer profile bridge.
-- Aligns with 001_thin_cloud_registry.sql schema.

create table if not exists public.developer_profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  email text not null,
  created_at timestamptz default now()
);

-- Auto-create developer row on auth signup
-- Note: developers table in 001 uses name (not display_name), auth_user_id references

create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.developers (auth_user_id, email, name)
  values (new.id, new.email, coalesce(new.raw_user_meta_data->>'full_name', ''));
  insert into public.developer_profiles (id, email)
  values (new.id, new.email);
  return new;
end;
$$ language plpgsql security definer;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- API key verification function.
-- api_keys columns from 001: id, developer_id, app_id, key_hash, key_prefix, env, is_active, last_used_at, created_at
create or replace function public.verify_api_key(key_text text)
returns table (
  key_id uuid,
  developer_id uuid,
  app_id text,
  env text,
  valid boolean
) as $$
begin
  return query
  select
    a.id as key_id,
    a.developer_id,
    a.app_id,
    a.env,
    (a.is_active = true) as valid
  from public.api_keys a
  where a.key_hash = crypt(key_text, a.key_hash)
  limit 1;
end;
$$ language plpgsql security definer;

-- Add last_used_at update helper
create or replace function public.touch_api_key(key_id uuid)
returns void as $$
begin
  update public.api_keys set last_used_at = now() where id = key_id;
end;
$$ language plpgsql security definer;
