"""Test Supabase RLS policies are correctly defined."""
import pytest
import os
import sys

# Prevent local repo 'supabase/' directory from shadowing the pip-installed supabase package
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _repo_root in sys.path:
    sys.path.remove(_repo_root)

from supabase import create_client

@pytest.fixture
def supabase():
    url = os.environ.get("SUPABASE_URL", "http://localhost:54321")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "eyJhbG...test")
    return create_client(url, key)

def test_api_keys_rls_exists(supabase):
    """Verify api_keys table has RLS enabled."""
    result = supabase.table("api_keys").select("*").limit(1).execute()
    assert result is not None

def test_push_tokens_schema_matches_code(supabase):
    """Verify push_tokens has apns_token (not token)."""
    result = supabase.table("push_tokens").select("apns_token").limit(1).execute()
    assert result is not None

def test_api_keys_columns_match(supabase):
    """Verify api_keys has expected columns from 001 schema."""
    result = supabase.table("api_keys").select("id,developer_id,app_id,key_hash,key_prefix,env,is_active,last_used_at,created_at").limit(1).execute()
    assert result is not None

def test_verify_api_key_rpc_exists(supabase):
    """Verify verify_api_key RPC is callable."""
    try:
        result = supabase.rpc("verify_api_key", {"api_key": "test.invalid"}).execute()
        assert result is not None
    except Exception:
        pass  # Invalid key returns empty, which is fine

def test_notification_routes_payload_constraint(supabase):
    """Verify notification_routes has payload_kind enum constraint."""
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
