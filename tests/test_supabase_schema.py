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
