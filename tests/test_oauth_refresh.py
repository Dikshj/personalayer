import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


class FakeOAuthResponse:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "access_token": "new_access_token",
            "refresh_token": "rotated_refresh_token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "https://www.googleapis.com/auth/gmail.metadata",
        }


def test_oauth_refresh_rotates_encrypted_token_without_exposing_secret(monkeypatch, tmp_path):
    import database
    import pcl.oauth as oauth

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'oauth_refresh.db')
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(oauth.httpx, "post", lambda *args, **kwargs: FakeOAuthResponse())
    database.create_tables()
    database.connect_pcl_integration(
        source="gmail",
        name="Gmail",
        scopes=["email_metadata"],
        metadata={"user_id": "user_1"},
        account_hint="user@example.com",
        auth_status="oauth_connected",
        auth_expires_at=1,
    )
    database.store_pcl_integration_oauth_token(
        source="gmail",
        user_id="user_1",
        token_payload={
            "access_token": "old_access_token",
            "refresh_token": "old_refresh_token",
            "token_type": "Bearer",
            "expires_at": 1,
        },
        scopes=["email_metadata"],
        expires_at=1,
    )

    result = oauth.refresh_oauth_token("gmail", user_id="user_1")
    token = database.get_decrypted_pcl_integration_oauth_token("gmail", "user_1")
    public_tokens = database.list_pcl_integration_oauth_tokens("user_1")

    assert result["status"] == "refreshed"
    assert token["access_token"] == "new_access_token"
    assert token["refresh_token"] == "rotated_refresh_token"
    assert public_tokens[0]["has_refresh_token"] is True
    assert "new_access_token" not in str(result)
    assert "rotated_refresh_token" not in str(public_tokens)


def test_sync_refreshes_expired_oauth_before_connector_job(monkeypatch, tmp_path):
    import database
    import pcl.oauth as oauth
    from pcl.integration_jobs import sync_integration

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'oauth_refresh_sync.db')
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setattr(oauth.httpx, "post", lambda *args, **kwargs: FakeOAuthResponse())
    database.create_tables()
    database.connect_pcl_integration(
        source="gmail",
        name="Gmail",
        scopes=["email_metadata"],
        metadata={
            "user_id": "user_1",
            "messages": [{
                "labels": ["Work"],
                "sender": "alex@example.com",
                "timestamp": 1700000000000,
            }],
        },
        account_hint="user@example.com",
        auth_status="oauth_connected",
        auth_expires_at=1,
    )
    database.store_pcl_integration_oauth_token(
        source="gmail",
        user_id="user_1",
        token_payload={
            "access_token": "old_access_token",
            "refresh_token": "old_refresh_token",
            "token_type": "Bearer",
            "expires_at": 1,
        },
        scopes=["email_metadata"],
        expires_at=1,
    )

    result = sync_integration("gmail", user_id="user_1")
    integration = database.get_pcl_integration("gmail")

    assert result["status"] == "ok"
    assert result["items_synced"] == 1
    assert integration["auth_expires_at"] > 1
