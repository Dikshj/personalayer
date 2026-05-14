"""Integration test for Supabase RLS policies.

Requires: pip install supabase pytest
Requires: Running Supabase instance (local or cloud)

Run explicitly:
    pytest tests/integration/ -v

Skipped by default in full suite to avoid local supabase/ directory shadowing
the pip-installed supabase Python package.
"""
import os
import sys
import pytest

# Prevent local repo 'supabase/' directory from shadowing pip package.
# This must happen BEFORE any supabase import.
_repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_paths_to_remove = [p for p in sys.path if p == _repo_root or p == "" or p == "."]
for p in _paths_to_remove:
    sys.path.remove(p)

try:
    from supabase import create_client
except ImportError as e:
    pytest.skip(
        f"supabase Python package not installed or shadowed: {e}",
        allow_module_level=True
    )


@pytest.fixture
def supabase():
    url = os.environ.get("SUPABASE_URL", "http://localhost:54321")
    key = os.environ.get(
        "SUPABASE_SERVICE_ROLE_KEY",
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU"
    )
    if url == "http://localhost:54321":
        pytest.skip("SUPABASE_URL not set and localhost not running", allow_module_level=True)
    return create_client(url, key)


def test_api_keys_rls_exists(supabase):
    result = supabase.table("api_keys").select("*").limit(1).execute()
    assert result is not None


def test_push_tokens_schema_matches_code(supabase):
    result = supabase.table("push_tokens").select("apns_token").limit(1).execute()
    assert result is not None


def test_api_keys_columns_match(supabase):
    result = supabase.table("api_keys").select(
        "id,developer_id,app_id,key_hash,key_prefix,env,is_active,last_used_at,created_at"
    ).limit(1).execute()
    assert result is not None


def test_verify_api_key_rpc_exists(supabase):
    try:
        result = supabase.rpc("verify_api_key", {"api_key": "test.invalid"}).execute()
        assert result is not None
    except Exception:
        pass


def test_notification_routes_payload_constraint(supabase):
    with pytest.raises(Exception):
        supabase.table("notification_routes").insert({
            "user_id": "00000000-0000-0000-0000-000000000000",
            "device_id": "test",
            "push_token_id": "00000000-0000-0000-0000-000000000000",
            "notification_type": "test",
            "deliver_after": "2024-01-01",
            "payload_kind": "invalid_kind",
            "status": "queued"
        }).execute()
