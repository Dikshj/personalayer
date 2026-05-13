import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


@pytest.fixture(autouse=True)
def use_test_db(monkeypatch, tmp_path):
    import database

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'proxy.db')
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    database.create_tables()


def test_context_steering_injects_system_prefix_and_removes_token():
    from pcl.contextlayer import ingest_context_event, update_active_context
    from pcl.proxy import inject_context_steering

    for _ in range(4):
        ingest_context_event(
            {
                "user_id": "user_1",
                "app_id": "docs_app",
                "feature_id": "outline",
                "action": "used",
                "timestamp": int(time.time() * 1000),
            },
            source="sdk",
        )
    update_active_context("user_1", project="Launch plan", active_apps=["docs_app"])

    payload = {
        "model": "gpt-test",
        "messages": [
            {"role": "user", "content": "Draft this with {cl_context}."},
        ],
    }

    steered, bundle = inject_context_steering(payload, user_id="user_1", app_id="docs_app")

    assert bundle["bundle_id"]
    assert steered["messages"][0]["role"] == "system"
    assert "[ContextLayer user profile]" in steered["messages"][0]["content"]
    assert "features_used: outline" in steered["messages"][0]["content"]
    assert "current_project: Launch plan" in steered["messages"][0]["content"]
    assert steered["messages"][1]["content"] == "Draft this with ."


def test_context_steering_leaves_payload_without_token_unchanged():
    from pcl.proxy import inject_context_steering

    payload = {
        "model": "gpt-test",
        "messages": [{"role": "user", "content": "No context here."}],
    }

    steered, bundle = inject_context_steering(payload)

    assert steered == payload
    assert bundle is None


def test_context_steering_enforces_contextlayer_developer_auth_when_present():
    import database
    from pcl.proxy import inject_context_steering

    developer = database.upsert_developer("dev@example.com", "Dev")
    database.register_developer_app(developer["id"], "docs_app", "Docs App")
    key = database.create_developer_api_key(developer["id"], app_id="docs_app")

    payload = {
        "model": "gpt-test",
        "messages": [{"role": "user", "content": "{cl_context} Draft."}],
    }
    denied, denied_bundle = inject_context_steering(
        payload,
        user_id="user_1",
        app_id="docs_app",
        context_authorization=f"Bearer {key['key']}",
    )
    database.grant_app_consent(
        "user_1",
        "docs_app",
        scopes=["context_steering"],
        developer_id=developer["id"],
    )
    steered, bundle = inject_context_steering(
        payload,
        user_id="user_1",
        app_id="docs_app",
        context_authorization=f"Bearer {key['key']}",
    )

    assert denied["error"] == "missing_user_consent"
    assert denied_bundle is None
    assert bundle["auth"]["mode"] == "developer"
    assert steered["messages"][0]["role"] == "system"


@pytest.mark.asyncio
async def test_chat_completion_endpoint_returns_dry_run(client):
    async with client as c:
        await c.post("/v1/ingest/sdk", json={
            "user_id": "user_1",
            "app_id": "mail_app",
            "feature_id": "smart-reply",
            "action": "used",
            "timestamp": int(time.time() * 1000),
        })
        response = await c.post("/v1/chat/completions", json={
            "model": "gpt-test",
            "user_id": "user_1",
            "app_id": "mail_app",
            "messages": [{"role": "user", "content": "{cl_context} Write a reply."}],
        })

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "dry_run"
    assert data["context_injected"] is True
    assert data["payload"]["messages"][0]["role"] == "system"
    assert data["payload"]["messages"][1]["content"] == "Write a reply."


@pytest.mark.asyncio
async def test_chat_completion_endpoint_uses_contextlayer_key_header(client):
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
            "/v1/chat/completions",
            headers={
                "x-contextlayer-api-key": raw_key,
                "x-user-token": "user:user_1",
            },
            json={
                "model": "gpt-test",
                "user_id": "ignored",
                "app_id": "mail_app",
                "messages": [{"role": "user", "content": "{cl_context} Write."}],
            },
        )
        await c.post("/v1/auth/consent", json={
            "user_id": "user_1",
            "app_id": "mail_app",
            "developer_id": developer_id,
            "scopes": ["context_steering"],
        })
        allowed = await c.post(
            "/v1/chat/completions",
            headers={
                "x-contextlayer-api-key": raw_key,
                "x-user-token": "user:user_1",
            },
            json={
                "model": "gpt-test",
                "user_id": "ignored",
                "app_id": "mail_app",
                "messages": [{"role": "user", "content": "{cl_context} Write."}],
            },
        )

    assert denied.json()["error"] == "missing_user_consent"
    assert allowed.json()["status"] == "dry_run"
    assert allowed.json()["context_injected"] is True


@pytest.fixture
def client(monkeypatch):
    from httpx import AsyncClient
    from main import app

    return AsyncClient(app=app, base_url="http://test")
