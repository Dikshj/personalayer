import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


@pytest.fixture(autouse=True)
def use_test_db(monkeypatch, tmp_path):
    import database

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'consent.db')
    database.create_tables()


def test_consent_grant_and_revoke_controls_v1_bundle():
    from database import get_app_permission, grant_app_consent, revoke_app_consent
    from pcl.contextlayer import build_context_bundle, ingest_context_event

    ingest_context_event(
        {
            "user_id": "user_1",
            "app_id": "mail_app",
            "feature_id": "smart-reply",
            "action": "used",
            "timestamp": int(time.time() * 1000),
        },
        source="sdk",
    )
    granted = grant_app_consent(
        user_id="user_1",
        app_id="mail_app",
        scopes=["getFeatureUsage", "getProfile"],
        developer_id="dev_1",
    )
    bundle = build_context_bundle("user_1", "mail_app", intent="full_profile")

    assert granted["is_active"] is True
    assert get_app_permission("user_1", "mail_app")["scopes"] == ["getFeatureUsage", "getProfile"]
    assert bundle["permission"]["status"] == "granted"
    assert revoke_app_consent("user_1", "mail_app") is True
    denied = build_context_bundle("user_1", "mail_app", intent="full_profile")
    assert denied["error"] == "app_consent_revoked"


def test_developer_registration_app_and_api_key_roundtrip():
    from database import (
        create_developer_api_key,
        list_developer_api_keys,
        register_developer_app,
        upsert_developer,
        verify_developer_api_key,
    )

    developer = upsert_developer("dev@example.com", "Dev")
    app = register_developer_app(developer["id"], "mail_app", "Mail App", "mail.example.com")
    key = create_developer_api_key(developer["id"], app_id="mail_app", env="test")
    keys = list_developer_api_keys(developer["id"])

    assert app["developer_id"] == developer["id"]
    assert key["key"].startswith("cl_test_")
    assert key["key_prefix"] == key["key"][:12]
    assert verify_developer_api_key(key["key"])["developer_id"] == developer["id"]
    assert "key" not in keys[0]
    assert keys[0]["app_id"] == "mail_app"


def test_developer_context_authorization_enforces_consent_and_scopes():
    from database import (
        create_developer_api_key,
        grant_app_consent,
        register_developer_app,
        upsert_developer,
    )
    from pcl.contextlayer import authorize_developer_context_request

    developer = upsert_developer("dev@example.com", "Dev")
    register_developer_app(developer["id"], "mail_app", "Mail App")
    key = create_developer_api_key(developer["id"], app_id="mail_app")

    missing = authorize_developer_context_request(
        f"Bearer {key['key']}",
        user_id="user_1",
        app_id="mail_app",
        requested_scopes=["getFeatureUsage"],
    )
    grant_app_consent("user_1", "mail_app", scopes=["getFeatureUsage"], developer_id=developer["id"])
    allowed = authorize_developer_context_request(
        f"Bearer {key['key']}",
        user_id="user_1",
        app_id="mail_app",
        requested_scopes=["getFeatureUsage"],
    )
    denied_scope = authorize_developer_context_request(
        f"Bearer {key['key']}",
        user_id="user_1",
        app_id="mail_app",
        requested_scopes=["getConstraints"],
    )

    assert missing["error"] == "missing_user_consent"
    assert allowed["authorized"] is True
    assert allowed["mode"] == "developer"
    assert denied_scope["error"] == "scope_not_granted"


@pytest.mark.asyncio
async def test_consent_and_developer_endpoints(client):
    async with client as c:
        developer = await c.post("/v1/developer/register", json={
            "email": "dev@example.com",
            "name": "Dev",
        })
        developer_id = developer.json()["developer"]["id"]
        app = await c.post("/v1/developer/apps", json={
            "developer_id": developer_id,
            "app_id": "mail_app",
            "name": "Mail App",
            "domain": "mail.example.com",
        })
        key = await c.post("/v1/developer/keys", json={
            "developer_id": developer_id,
            "app_id": "mail_app",
            "env": "test",
        })
        keys = await c.get("/v1/developer/keys", params={"developer_id": developer_id})
        consent = await c.post("/v1/auth/consent", json={
            "user_id": "user_1",
            "app_id": "mail_app",
            "developer_id": developer_id,
            "scopes": ["getFeatureUsage"],
        })
        consents = await c.get("/v1/auth/consent", params={"user_id": "user_1"})
        revoked = await c.delete("/v1/auth/consent/mail_app", params={"user_id": "user_1"})

    assert app.json()["app"]["app_id"] == "mail_app"
    assert key.json()["api_key"]["key"].startswith("cl_test_")
    assert "key" not in keys.json()["keys"][0]
    assert consent.json()["status"] == "granted"
    assert consents.json()["permissions"][0]["app_id"] == "mail_app"
    assert revoked.json()["status"] == "revoked"


@pytest.mark.asyncio
async def test_context_bundle_endpoint_accepts_developer_auth_after_consent(client):
    async with client as c:
        developer = await c.post("/v1/developer/register", json={
            "email": "dev@example.com",
            "name": "Dev",
        })
        developer_id = developer.json()["developer"]["id"]
        await c.post("/v1/developer/apps", json={
            "developer_id": developer_id,
            "app_id": "mail_app",
            "name": "Mail App",
        })
        key = await c.post("/v1/developer/keys", json={
            "developer_id": developer_id,
            "app_id": "mail_app",
        })
        raw_key = key.json()["api_key"]["key"]
        denied = await c.post(
            "/v1/context/bundle",
            headers={"Authorization": f"Bearer {raw_key}", "x-user-token": "user:user_1"},
            json={
                "user_id": "ignored",
                "app_id": "mail_app",
                "intent": "adapt_ui",
                "requested_scopes": ["getFeatureUsage"],
            },
        )
        await c.post("/v1/auth/consent", json={
            "user_id": "user_1",
            "app_id": "mail_app",
            "developer_id": developer_id,
            "scopes": ["getFeatureUsage"],
        })
        allowed = await c.post(
            "/v1/context/bundle",
            headers={"Authorization": f"Bearer {raw_key}", "x-user-token": "user:user_1"},
            json={
                "user_id": "ignored",
                "app_id": "mail_app",
                "intent": "adapt_ui",
                "requested_scopes": ["getFeatureUsage"],
            },
        )

    assert denied.json()["error"] == "missing_user_consent"
    assert allowed.json()["auth"]["mode"] == "developer"
    assert allowed.json()["permission"]["status"] == "granted"


@pytest.fixture
def client():
    from httpx import AsyncClient
    from main import app

    return AsyncClient(app=app, base_url="http://test")
