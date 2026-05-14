# tests/test_main.py
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import time
from unittest.mock import MagicMock


@pytest.fixture(autouse=True)
def use_test_db(monkeypatch, tmp_path):
    import database
    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'test_main.db')
    database.create_tables()
    # Prevent real APScheduler from starting in tests
    import main
    monkeypatch.setattr(main, 'create_scheduler',
                        lambda: MagicMock(start=lambda: None, shutdown=lambda: None))


@pytest.fixture
def client():
    from httpx import AsyncClient
    from main import app
    return AsyncClient(app=app, base_url="http://test")


@pytest.mark.asyncio
async def test_health_endpoint(client):
    async with client as c:
        resp = await c.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_daemon_status_endpoint(client):
    async with client as c:
        resp = await c.get("/daemon/status")
    data = resp.json()
    assert resp.status_code == 200
    assert data["mode"] == "local_context_daemon"
    assert "browser_extension" in data["collectors"]
    browser_spec = next(
        spec for spec in data["collector_specs"]
        if spec["source"] == "browser_extension"
    )
    assert browser_spec["event_types"] == ["browser_activity"]
    assert browser_spec["raw_content_stored"] is False
    assert data["policy"]["scoped_context_contracts"] is True


@pytest.mark.asyncio
async def test_event_stored(client):
    from database import get_events_last_n_days
    async with client as c:
        resp = await c.post("/event", json={
            "url": "https://github.com/anthropics/mcp",
            "title": "MCP Python SDK",
            "time_spent_seconds": 180,
            "timestamp": int(time.time() * 1000)
        })
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    events = get_events_last_n_days(1)
    assert len(events) == 1
    assert events[0]["domain"] == "github.com"


@pytest.mark.asyncio
async def test_localhost_events_skipped(client):
    from database import get_events_last_n_days
    async with client as c:
        resp = await c.post("/event", json={
            "url": "http://localhost:3000/dashboard",
            "title": "Local Dev",
            "time_spent_seconds": 10,
            "timestamp": int(time.time() * 1000)
        })
    assert resp.json()["status"] == "skipped"
    assert get_events_last_n_days(1) == []


@pytest.mark.asyncio
async def test_search_query_extracted(client):
    from database import get_events_last_n_days
    async with client as c:
        await c.post("/event", json={
            "url": "https://www.google.com/search?q=mcp+server+tutorial",
            "title": "mcp server tutorial - Google Search",
            "time_spent_seconds": 5,
            "timestamp": int(time.time() * 1000)
        })
    events = get_events_last_n_days(1)
    assert events[0]["search_query"] == "mcp server tutorial"


@pytest.mark.asyncio
async def test_context_contract_lifecycle_endpoints(client):
    async with client as c:
        negotiate = await c.post("/context/negotiate", json={
            "platform_type": "email_service",
            "facilities": ["reply_drafting"],
            "requested_context": ["communication_style"],
            "purpose": "draft replies",
        })
        contract_id = negotiate.json()["contract_id"]

        contracts = await c.get("/context-contracts")
        assert contracts.json()["contracts"][0]["contract_id"] == contract_id

        scoped = await c.get(f"/context/{contract_id}")
        assert scoped.status_code == 200

        logs = await c.get("/context-access-log", params={"contract_id": contract_id})
        assert logs.json()["logs"][0]["action"] == "scoped_persona_returned"

        revoke = await c.post(f"/context/{contract_id}/revoke")
        assert revoke.json()["status"] == "revoked"

        denied = await c.get(f"/context/{contract_id}")
        assert denied.json()["error"] == "contract_revoked"


@pytest.mark.asyncio
async def test_persona_feedback_endpoint(client):
    async with client as c:
        resp = await c.post("/persona/feedback", json={
            "signal_type": "interest",
            "name": "crypto",
            "action": "reject",
            "reason": "not a real interest",
        })
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["feedback"]["action"] == "reject"


@pytest.mark.asyncio
async def test_activity_summary_endpoint(client):
    async with client as c:
        await c.post("/event", json={
            "url": "https://github.com/modelcontextprotocol/python-sdk",
            "title": "MCP Python SDK",
            "time_spent_seconds": 120,
            "timestamp": int(time.time() * 1000),
        })
        resp = await c.get("/activity/summary", params={"days": 7})

    data = resp.json()
    assert resp.status_code == 200
    assert data["days"] == 7
    assert data["events"] == 1
    assert data["persona_signals"] > 0


@pytest.mark.asyncio
async def test_next_context_prediction_endpoint(client):
    async with client as c:
        await c.post("/feed-event", json={
            "source": "claude_code",
            "content_type": "session_signals",
            "content": "[claude_code] task:building | domain:ai_ml | langs:python | tools:fastapi,mcp",
            "author": "user",
            "url": "session.jsonl",
            "timestamp": int(time.time() * 1000),
        })
        resp = await c.get("/predictions/next-context", params={"days": 7})

    data = resp.json()
    assert resp.status_code == 200
    assert data["meta"]["model"] == "local_behavior_prediction_v1"
    assert "needed_context" in data["prediction"]


@pytest.mark.asyncio
async def test_pcl_query_endpoint_returns_decision_bundle(client):
    async with client as c:
        await c.post("/pcl/apps", json={
            "app_id": "mail_app",
            "name": "Mail App",
            "allowed_layers": ["identity_role", "active_context"],
        })
        resp = await c.post("/pcl/query", json={
            "app_id": "mail_app",
            "user_id": "user_1",
            "requested_layers": ["identity_role", "capability_signals"],
            "features": [
                {"feature_id": "smart_reply", "name": "Smart Reply"},
                {"feature_id": "newsletter_filter", "name": "Newsletter Filter"},
            ],
        })
        logs = await c.get("/pcl/query-log", params={"app_id": "mail_app"})

    data = resp.json()
    assert resp.status_code == 200
    assert data["app_id"] == "mail_app"
    assert data["audit"]["raw_data_shared"] is False
    assert data["audit"]["log_id"]
    assert len(data["ranked_features"]) == 2
    assert "identity_role" in data["allowed_layers"]
    assert "capability_signals" not in data["allowed_layers"]
    assert logs.json()["logs"][0]["status"] == "returned"


@pytest.mark.asyncio
async def test_pcl_query_denies_unknown_or_revoked_app(client):
    async with client as c:
        unknown = await c.post("/pcl/query", json={
            "app_id": "unknown_app",
            "user_id": "user_1",
            "features": [{"feature_id": "smart_reply", "name": "Smart Reply"}],
        })

        await c.post("/pcl/apps", json={
            "app_id": "revoked_app",
            "name": "Revoked App",
            "allowed_layers": ["identity_role"],
        })
        await c.post("/pcl/apps/revoked_app/revoke")
        revoked = await c.post("/pcl/query", json={
            "app_id": "revoked_app",
            "user_id": "user_1",
            "features": [{"feature_id": "smart_reply", "name": "Smart Reply"}],
        })

    assert unknown.json()["error"] == "unknown_app"
    assert unknown.json()["audit"]["query_logged"] is True
    assert revoked.json()["error"] == "app_revoked"


@pytest.mark.asyncio
async def test_pcl_onboarding_seed_feeds_query_profile(client):
    async with client as c:
        questions = await c.get("/pcl/onboarding/questions")
        seed = await c.post("/pcl/onboarding/seed", json={
            "user_id": "user_seeded",
            "answers": {
                "identity": "Founder, developer tools",
                "features": "Inbox Zero",
                "behavior": "quick minimal flows",
                "active_context": "building PCL",
                "preferences": "never show AI Summary",
            },
        })
        await c.post("/pcl/apps", json={
            "app_id": "seeded_app",
            "name": "Seeded App",
            "allowed_layers": [
                "identity_role",
                "capability_signals",
                "behavior_patterns",
                "active_context",
                "explicit_preferences",
            ],
        })
        query = await c.post("/pcl/query", json={
            "app_id": "seeded_app",
            "user_id": "user_seeded",
            "features": [
                {"feature_id": "inbox_zero", "name": "Inbox Zero"},
                {"feature_id": "ai_summary", "name": "AI Summary"},
            ],
        })

    data = query.json()
    assert len(questions.json()["questions"]) == 5
    assert seed.json()["profile_seed"]["identity"]["role"] == "Founder"
    assert data["context"]["identity_role"]["role"] == "Founder"
    assert data["ranked_features"][0]["feature_id"] == "inbox_zero"
    assert data["ranked_features"][-1]["feature_id"] == "ai_summary"


@pytest.mark.asyncio
async def test_pcl_feature_event_feeds_capability_ranking(client):
    now_ms = int(time.time() * 1000)
    async with client as c:
        await c.post("/pcl/apps", json={
            "app_id": "product_app",
            "name": "Product App",
            "allowed_layers": ["capability_signals"],
        })
        event = await c.post("/pcl/events/feature", json={
            "app_id": "product_app",
            "user_id": "user_featured",
            "feature_id": "kanban",
            "feature_name": "Kanban",
            "event_type": "used",
            "weight": 1.0,
            "metadata": {"raw_note": "email user@example.com"},
            "timestamp": now_ms,
        })
        query = await c.post("/pcl/query", json={
            "app_id": "product_app",
            "user_id": "user_featured",
            "features": [
                {"feature_id": "calendar", "name": "Calendar"},
                {"feature_id": "kanban", "name": "Kanban"},
            ],
        })
        usage = await c.get("/pcl/feature-usage", params={"user_id": "user_featured"})
        profile = await c.get("/pcl/profile", params={"user_id": "user_featured"})

    data = query.json()
    assert event.json()["status"] == "ok"
    assert event.json()["event"]["metadata"] == {}
    assert data["ranked_features"][0]["feature_id"] == "kanban"
    assert "feature_usage" in data["ranked_features"][0]["reason_codes"]
    assert usage.json()["features"][0]["feature_id"] == "kanban"
    assert profile.json()["capabilities"][0]["feature_id"] == "kanban"


@pytest.mark.asyncio
async def test_pcl_feature_event_denies_unregistered_app(client):
    async with client as c:
        resp = await c.post("/pcl/events/feature", json={
            "app_id": "missing_app",
            "user_id": "user_1",
            "feature_id": "smart_reply",
            "timestamp": int(time.time() * 1000),
        })

    assert resp.json()["error"] == "unknown_app"


@pytest.mark.asyncio
async def test_pcl_onboarding_seed_get_endpoint(client):
    async with client as c:
        missing = await c.get("/pcl/onboarding/seed", params={"user_id": "missing"})
        await c.post("/pcl/onboarding/seed", json={
            "user_id": "seed_lookup",
            "answers": {"identity": "Founder, developer tools"},
        })
        found = await c.get("/pcl/onboarding/seed", params={"user_id": "seed_lookup"})

    assert missing.json()["error"] == "not_found"
    assert found.json()["profile_seed"]["identity"]["role"] == "Founder"


@pytest.mark.asyncio
async def test_pcl_integration_endpoints(client):
    async with client as c:
        catalog = await c.get("/pcl/integrations/catalog")
        initial = await c.get("/pcl/integrations")
        connected = await c.post("/pcl/integrations/gmail/connect", json={
            "account_hint": "user@example.com",
            "auth_status": "authorized",
            "metadata": {
                "messages": [
                    {
                        "from": "person@example.com",
                        "labels": ["Work"],
                        "timestamp": 1700000000000,
                        "access_token": "ghp_secretsecretsecret",
                    }
                ]
            },
        })
        synced = await c.post("/pcl/integrations/gmail/sync")
        after_sync = await c.get("/pcl/integrations")
        disconnected = await c.post("/pcl/integrations/gmail/disconnect")
        unknown = await c.post("/pcl/integrations/unknown/connect", json={})

    assert "gmail" in {item["source"] for item in catalog.json()["integrations"]}
    gmail_catalog = next(item for item in catalog.json()["integrations"] if item["source"] == "gmail")
    assert gmail_catalog["auth_type"] == "oauth_or_local_metadata"
    assert "messages" in gmail_catalog["metadata_example"]
    assert next(item for item in initial.json()["integrations"] if item["source"] == "gmail")["status"] == "available"
    assert connected.json()["status"] == "connected"
    assert synced.json()["status"] == "ok"
    gmail = next(item for item in after_sync.json()["integrations"] if item["source"] == "gmail")
    assert gmail["account_hint"] == "user@example.com"
    assert gmail["auth_status"] == "authorized"
    assert "access_token" not in str(gmail["metadata"])
    assert gmail["last_sync_status"] == "ok"
    assert gmail["items_synced"] == 1
    assert disconnected.json()["status"] == "disconnected"
    assert unknown.json()["error"] == "unknown_integration"


@pytest.mark.asyncio
async def test_pcl_github_integration_sync_endpoint(client, monkeypatch):
    import collectors.github

    monkeypatch.setattr(collectors.github, "collect_github", lambda username: 3)

    async with client as c:
        await c.post("/pcl/integrations/github/connect", json={
            "metadata": {"username": "octocat"},
        })
        synced = await c.post("/pcl/integrations/github/sync")
        integrations = await c.get("/pcl/integrations")

    github = next(item for item in integrations.json()["integrations"] if item["source"] == "github")
    assert synced.json()["status"] == "ok"
    assert synced.json()["items_synced"] == 3
    assert github["last_sync_status"] == "ok"


@pytest.mark.asyncio
async def test_context_shared_bundle_endpoint_reads_local_file(client):
    async with client as c:
        missing = await c.get("/v1/context/shared-bundle", params={"user_id": "user_1"})
        await c.post("/v1/ingest/sdk", json={
            "user_id": "user_1",
            "app_id": "figma",
            "feature_id": "auto-layout",
            "action": "used",
            "session_id": "s1",
            "timestamp": int(time.time() * 1000),
        })
        await c.post("/v1/jobs/daily-refresh", json={
            "user_id": "user_1",
            "timezone": "UTC",
        })
        found = await c.get("/v1/context/shared-bundle", params={"user_id": "user_1"})

    assert missing.json()["error"] == "shared_bundle_not_found"
    data = found.json()
    assert data["status"] == "ok"
    assert data["source"] == "local_shared_context_file"
    assert data["bundle"]["privacy"]["raw_events_included"] is False
    assert data["bundle"]["features"][0]["feature_id"] == "auto-layout"


@pytest.mark.asyncio
async def test_device_push_token_and_notification_route_endpoints(client):
    async with client as c:
        registered = await c.post("/v1/devices/push-token", json={
            "user_id": "user_1",
            "device_id": "iphone-1",
            "apns_token": "apns_token_123456789",
            "platform": "ios",
            "environment": "sandbox",
        })
        tokens = await c.get("/v1/devices/push-token", params={"user_id": "user_1"})
        await c.post("/v1/ingest/sdk", json={
            "user_id": "user_1",
            "app_id": "figma",
            "feature_id": "auto-layout",
            "action": "used",
            "timestamp": int(time.time() * 1000),
        })
        await c.post("/v1/jobs/daily-refresh", json={"user_id": "user_1"})
        routes = await c.get("/v1/notifications/routes", params={"user_id": "user_1"})
        revoked = await c.delete("/v1/devices/push-token/iphone-1", params={"user_id": "user_1"})

    assert registered.json()["status"] == "registered"
    assert tokens.json()["tokens"][0]["token_prefix"] == "apns_token_1"
    route = routes.json()["routes"][0]
    assert route["notification_type"] == "daily_insight_ready"
    assert route["payload_kind"] == "silent_local_insight"
    assert "auto-layout" not in str(route)
    assert revoked.json()["status"] == "revoked"


@pytest.mark.asyncio
async def test_pcl_integration_oauth_flow_endpoints(client, monkeypatch):
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_ID", raising=False)

    async with client as c:
        missing_config = await c.post("/pcl/integrations/gmail/oauth/start", json={
            "user_id": "user_1",
            "redirect_uri": "http://localhost/callback",
        })
        callback = await c.post("/pcl/integrations/oauth/callback", json={
            "state": missing_config.json()["state"],
            "code": "local-code",
            "account_hint": "user@example.com",
        })
        integrations = await c.get("/pcl/integrations")
        tokens = await c.get("/pcl/integrations/oauth/tokens", params={"user_id": "user_1"})
        revoked_token = await c.delete("/pcl/integrations/gmail/oauth/token", params={"user_id": "user_1"})
        invalid = await c.post("/pcl/integrations/oauth/callback", json={
            "state": missing_config.json()["state"],
            "code": "local-code",
        })
        unsupported = await c.post("/pcl/integrations/github/oauth/start", json={
            "user_id": "user_1",
            "redirect_uri": "http://localhost/callback",
        })

    gmail = next(item for item in integrations.json()["integrations"] if item["source"] == "gmail")
    assert missing_config.json()["status"] == "configuration_required"
    assert missing_config.json()["client_id_env"] == "GOOGLE_OAUTH_CLIENT_ID"
    assert callback.json()["status"] == "connected"
    assert gmail["account_hint"] == "user@example.com"
    assert gmail["auth_status"] == "oauth_connected_local_token_store"
    assert gmail["auth_expires_at"]
    assert tokens.json()["tokens"][0]["has_refresh_token"] is True
    assert "local-code" not in str(tokens.json())
    assert "local_access" not in str(tokens.json())
    assert revoked_token.json()["status"] == "revoked"
    assert invalid.json()["error"] == "invalid_or_consumed_state"
    assert unsupported.json()["error"] == "oauth_not_supported"


@pytest.mark.asyncio
async def test_pcl_delete_controls(client):
    async with client as c:
        await c.post("/pcl/apps", json={
            "app_id": "delete_control_app",
            "name": "Delete Control App",
            "allowed_layers": ["identity_role"],
        })
        await c.post("/pcl/onboarding/seed", json={
            "user_id": "delete_control_user",
            "answers": {"identity": "operator"},
        })
        await c.post("/pcl/events/feature", json={
            "app_id": "delete_control_app",
            "user_id": "delete_control_user",
            "feature_id": "inbox",
            "feature_name": "Inbox",
            "event_type": "used",
            "weight": 1,
            "metadata": {},
            "timestamp": 1700000000000,
        })
        await c.post("/pcl/query", json={
            "app_id": "delete_control_app",
            "user_id": "delete_control_user",
            "purpose": "ui_personalization",
            "requested_layers": ["identity_role"],
            "features": [{"feature_id": "inbox", "name": "Inbox"}],
        })

        user_deleted = await c.delete("/pcl/users/delete_control_user/data")
        seed_after_delete = await c.get("/pcl/onboarding/seed", params={"user_id": "delete_control_user"})

        await c.post("/pcl/events/feature", json={
            "app_id": "delete_control_app",
            "user_id": "other_user",
            "feature_id": "inbox",
            "feature_name": "Inbox",
            "event_type": "used",
            "weight": 1,
            "metadata": {},
            "timestamp": 1700000000000,
        })
        app_deleted = await c.delete("/pcl/apps/delete_control_app/data")
        apps_after_delete = await c.get("/pcl/apps")

        await c.post("/pcl/integrations/gmail/connect", json={"metadata": {}})
        integration_deleted = await c.delete("/pcl/integrations/gmail/data")
        integrations_after_delete = await c.get("/pcl/integrations")

    assert user_deleted.json()["deleted"]["onboarding_seeds"] == 1
    assert user_deleted.json()["deleted"]["feature_events"] == 1
    assert user_deleted.json()["deleted"]["query_logs"] == 1
    assert seed_after_delete.json()["error"] == "not_found"
    assert app_deleted.json()["status"] == "deleted"
    assert not any(app["app_id"] == "delete_control_app" for app in apps_after_delete.json()["apps"])
    assert integration_deleted.json()["deleted"]["integrations"] == 1
    gmail = next(item for item in integrations_after_delete.json()["integrations"] if item["source"] == "gmail")
    assert gmail["status"] == "available"
