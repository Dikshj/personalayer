from pathlib import Path


FORBIDDEN_CLOUD_TERMS = {
    "raw_events",
    "temporal_chains",
    "kg_nodes",
    "kg_edges",
    "context_bundles",
    "feature_signals",
    "pcl_feature_events",
    "persona_signals",
    "abstract_attributes",
    "embedding",
}


def test_supabase_schema_stays_thin_cloud_only():
    migration = Path("supabase/migrations/001_thin_cloud_registry.sql").read_text(encoding="utf-8").lower()
    allowed_tables = {
        "developers",
        "apps",
        "api_keys",
        "app_permissions",
        "push_tokens",
        "notification_routes",
    }

    for table in allowed_tables:
        assert f"create table if not exists public.{table}" in migration
    for term in FORBIDDEN_CLOUD_TERMS:
        assert term not in migration
    assert "enable row level security" in migration
    assert "payload_kind must not contain behavioral text" in migration


def test_supabase_deploy_scaffold_has_no_secrets_or_processing_paths():
    config = Path("supabase/config.toml").read_text(encoding="utf-8").lower()
    env_example = Path(".env.example").read_text(encoding="utf-8").lower()

    assert "edge_runtime" in config
    assert "enabled = false" in config
    assert "storage" in config
    assert "service_role_key=\n" in env_example
    assert "apns_" in env_example
    for term in FORBIDDEN_CLOUD_TERMS:
        assert term not in config


def test_supabase_sync_and_observability_migrations_are_rls_protected():
    sync = Path("supabase/migrations/003_encrypted_summary_sync.sql").read_text(encoding="utf-8").lower()
    observability = Path("supabase/migrations/004_cloud_observability.sql").read_text(encoding="utf-8").lower()

    for table in ["sync_devices", "encrypted_summary_blobs", "sync_conflicts"]:
        assert f"create table if not exists public.{table}" in sync
        assert f"alter table public.{table} enable row level security" in sync
    assert "encrypted_blob jsonb not null" in sync
    assert "raw_events" not in sync
    assert "persona_signals" not in sync

    assert "create table if not exists public.observability_events" in observability
    assert "alter table public.observability_events enable row level security" in observability
    assert "attributes jsonb" in observability
    assert "must not contain personal content" in observability
