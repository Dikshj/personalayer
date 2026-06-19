# tests/test_main.py
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import time
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse


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
async def test_pcl_skill_registry_lifecycle(client):
    async with client as c:
        created = await c.post("/pcl/skills", json={
            "skill_id": "personal-writing-style",
            "name": "Personal Writing Style",
            "category": "writing",
            "description": "Drafts text in the user's confirmed tone.",
            "instructions": "Use voice.md and approved examples before drafting.",
            "allowed_layers": ["explicit_preferences", "active_context"],
            "memory_scopes": ["voice", "preferences"],
            "required_tools": ["memory.search"],
            "privacy_rules": ["never include raw private notes"],
        })
        listed = await c.get("/pcl/skills", params={"category": "writing"})
        fetched = await c.get("/pcl/skills/personal-writing-style")
        disabled = await c.post("/pcl/skills/personal-writing-style/disable")
        active = await c.get("/pcl/skills")
        all_skills = await c.get("/pcl/skills", params={"active_only": False})

    assert created.status_code == 200
    assert created.json()["skill_id"] == "personal-writing-style"
    assert created.json()["allowed_layers"] == ["explicit_preferences", "active_context"]
    assert listed.json()["skills"][0]["name"] == "Personal Writing Style"
    assert fetched.json()["memory_scopes"] == ["voice", "preferences"]
    assert disabled.json()["status"] == "disabled"
    assert active.json()["skills"] == []
    assert all_skills.json()["skills"][0]["status"] == "disabled"


@pytest.mark.asyncio
async def test_pcl_skill_router_selects_relevant_skills(client):
    async with client as c:
        await c.post("/pcl/skills", json={
            "skill_id": "personal-writing-style",
            "name": "Personal Writing Style",
            "category": "writing",
            "description": "Drafts email replies and messages in the user's tone.",
            "instructions": "Use voice.md, preferences.md, and approved writing examples.",
            "allowed_layers": ["explicit_preferences", "active_context"],
            "memory_scopes": ["voice", "preferences"],
            "required_tools": ["memory.search"],
            "privacy_rules": ["never include raw private notes"],
        })
        await c.post("/pcl/skills", json={
            "skill_id": "code-review",
            "name": "Code Review",
            "category": "coding",
            "description": "Reviews code changes, bugs, tests, and API design.",
            "allowed_layers": ["capability_signals", "active_context"],
            "memory_scopes": ["projects", "work-style"],
            "required_tools": ["repo.inspect"],
        })
        await c.put("/v1/memory/voice", json={
            "user_id": "user_1",
            "content": "# Voice\n\nKeep writing concise and direct.\n",
        })
        routed = await c.post("/pcl/skills/route", json={
            "user_id": "user_1",
            "message": "Write this email reply like me and keep my tone concise.",
            "max_skills": 2,
            "include_memory": True,
        })

    data = routed.json()
    assert routed.status_code == 200
    assert data["selected_skill_ids"][0] == "personal-writing-style"
    assert "voice" in data["memory_scopes"]
    assert "memory.search" in data["required_tools"]
    assert "never include raw private notes" in data["privacy_rules"]
    assert data["memory"][0]["scope"] == "voice"
    assert "concise and direct" in data["memory"][0]["content"]


@pytest.mark.asyncio
async def test_markdown_memory_lifecycle_endpoints(client):
    async with client as c:
        initialized = await c.post("/v1/memory/init", params={"user_id": "user_1"})
        files = await c.get("/v1/memory/files", params={"user_id": "user_1"})
        written = await c.put("/v1/memory/voice", json={
            "user_id": "user_1",
            "content": "# Voice\n\nPrefers concise, direct technical writing.\n",
        })
        appended = await c.post("/v1/memory/projects/append", json={
            "user_id": "user_1",
            "heading": "PersonaLayer",
            "entry": "Building a local-first persona layer with skills and memory.",
        })
        search = await c.post("/v1/memory/search", json={
            "user_id": "user_1",
            "query": "concise technical writing",
            "scopes": ["voice", "projects"],
        })
        decay = await c.post("/v1/memory/quality/decay", json={
            "user_id": "user_1",
            "scopes": ["voice", "projects"],
        })

    assert initialized.status_code == 200
    assert initialized.json()["total"] >= 10
    assert any(item["scope"] == "voice" for item in files.json()["files"])
    assert written.json()["scope"] == "voice"
    assert "concise, direct technical writing" in written.json()["content"]
    assert "PersonaLayer" in appended.json()["content"]
    assert search.json()["mode"] in {"hybrid", "indexed_hybrid"}
    assert search.json()["results"][0]["scope"] == "voice"
    assert "semantic_score" in search.json()["results"][0]
    assert search.json()["results"][0]["quality"]["confidence"] > 0
    assert len(decay.json()["scores"]) == 2
    assert decay.json()["scores"][0]["score"] >= 0


@pytest.mark.asyncio
async def test_markdown_memory_dedupes_prunes_and_indexes(client):
    async with client as c:
        first = await c.post("/v1/memory/projects/append", json={
            "user_id": "user_1",
            "heading": "PersonaLayer",
            "entry": "Building PersonaLayer with source-specific ingestion.",
            "source": "test",
        })
        duplicate = await c.post("/v1/memory/projects/append", json={
            "user_id": "user_1",
            "heading": "PersonaLayer",
            "entry": "Building PersonaLayer with source-specific ingestion.",
            "source": "test",
        })
        await c.post("/v1/memory/projects/append", json={
            "user_id": "user_1",
            "entry": "This old thing is not relevant anymore.",
            "source": "test",
        })
        search = await c.post("/v1/memory/search", json={
            "user_id": "user_1",
            "query": "source specific ingestion",
            "scopes": ["projects"],
        })
        memory = await c.get("/v1/memory/projects", params={"user_id": "user_1"})

    assert first.json()["content"].count("source-specific ingestion") == 1
    assert duplicate.json()["content"].count("source-specific ingestion") == 1
    assert search.json()["mode"] == "indexed_hybrid"
    assert search.json()["results"][0]["scope"] == "projects"
    assert search.json()["results"][0]["quality"]["source_count"] >= 1
    assert "not relevant anymore" not in memory.json()["content"]


def test_markdown_memory_rejects_unsafe_scope(tmp_path, monkeypatch):
    import database
    from pcl.memory import memory_file_path

    monkeypatch.setattr(database, "DATA_DIR", tmp_path)

    with pytest.raises(ValueError):
        memory_file_path("user_1", "../secrets")


@pytest.mark.asyncio
async def test_persona_memory_diff_approval_flow(client):
    async with client as c:
        await c.put("/v1/memory/voice", json={
            "user_id": "user_1",
            "content": "# Voice\n\nExisting memory.\n",
        })
        proposed = await c.post("/v1/memory/diffs", json={
            "user_id": "user_1",
            "scope": "voice",
            "proposed_content": "Prefers short, direct implementation notes.",
            "reason": "User corrected assistant verbosity.",
            "source": "reflection",
            "auto_apply": False,
        })
        diff_id = proposed.json()["id"]
        pending = await c.get("/v1/memory/diffs", params={"user_id": "user_1", "status": "pending"})
        approved = await c.post(f"/v1/memory/diffs/{diff_id}/approve", json={
            "reviewer_note": "accurate",
        })
        applied = await c.post(f"/v1/memory/diffs/{diff_id}/apply", json={
            "reviewer_note": "write to voice memory",
        })
        memory = await c.get("/v1/memory/voice", params={"user_id": "user_1"})

    assert proposed.status_code == 200
    assert proposed.json()["status"] == "pending"
    assert proposed.json()["current_excerpt"].endswith("Existing memory.\n")
    assert pending.json()["diffs"][0]["id"] == diff_id
    assert approved.json()["status"] == "approved"
    assert applied.json()["status"] == "applied"
    assert "Prefers short, direct implementation notes." in memory.json()["content"]


@pytest.mark.asyncio
async def test_persona_memory_diff_reject_does_not_write_memory(client):
    async with client as c:
        await c.put("/v1/memory/preferences", json={
            "user_id": "user_1",
            "content": "# Preferences\n\nExisting preferences.\n",
        })
        proposed = await c.post("/v1/memory/diffs", json={
            "user_id": "user_1",
            "scope": "preferences",
            "proposed_content": "Incorrect inferred preference.",
            "reason": "Low confidence.",
            "source": "reflection",
            "auto_apply": False,
        })
        diff_id = proposed.json()["id"]
        rejected = await c.post(f"/v1/memory/diffs/{diff_id}/reject", json={
            "reviewer_note": "wrong inference",
        })
        apply_after_reject = await c.post(f"/v1/memory/diffs/{diff_id}/apply", json={})
        memory = await c.get("/v1/memory/preferences", params={"user_id": "user_1"})

    assert rejected.json()["status"] == "rejected"
    assert apply_after_reject.json()["error"] == "not_found_or_not_applicable"
    assert "Incorrect inferred preference." not in memory.json()["content"]


@pytest.mark.asyncio
async def test_persona_memory_diff_auto_applies_by_default(client):
    async with client as c:
        proposed = await c.post("/v1/memory/diffs", json={
            "user_id": "user_1",
            "scope": "projects",
            "proposed_content": "Building PersonaLayer with automatic memory ingestion.",
            "reason": "Relevant active project.",
            "source": "reflection",
        })
        memory = await c.get("/v1/memory/projects", params={"user_id": "user_1"})
        diffs = await c.get("/v1/memory/diffs", params={"user_id": "user_1", "status": "applied"})

    assert proposed.json()["status"] == "applied"
    assert "automatic memory ingestion" in memory.json()["content"]
    assert diffs.json()["diffs"][0]["status"] == "applied"


@pytest.mark.asyncio
async def test_memory_forget_and_source_toggle_controls(client):
    async with client as c:
        await c.put("/v1/memory/projects", json={
            "user_id": "user_1",
            "content": "# Projects\n\nBad memory.\n",
            "source": "manual",
            "reason": "setup",
        })
        deleted = await c.request("DELETE", "/v1/memory/projects", json={
            "user_id": "user_1",
            "reason": "not relevant anymore",
        })
        disabled = await c.put("/v1/memory/sources/calendar", json={
            "user_id": "user_1",
            "enabled": False,
            "reason": "do not learn from calendar",
        })
        skipped = await c.post("/v1/memory/diffs", json={
            "user_id": "user_1",
            "scope": "daily-log",
            "proposed_content": "Calendar memory that should not be saved.",
            "source": "calendar",
            "reason": "source disabled",
        })
        sources = await c.get("/v1/memory/sources", params={"user_id": "user_1"})
        audit = await c.get("/v1/control-center/audit", params={"user_id": "user_1"})

    assert deleted.json()["deleted"] is True
    assert disabled.json()["enabled"] is False
    assert skipped.json()["status"] == "skipped_source_disabled"
    assert sources.json()["sources"][0]["source"] == "calendar"
    actions = {item["action"] for item in audit.json()["logs"]}
    assert "memory_forgotten" in actions
    assert "memory_source_toggled" in actions


@pytest.mark.asyncio
async def test_messaging_bridge_ingests_to_memory(client):
    async with client as c:
        ingested = await c.post("/v1/messaging/whatsapp/messages", json={
            "user_id": "user_1",
            "sender": "Alex",
            "thread_id": "yc-prep",
            "text": "Let's prep the YC application tomorrow.",
        })
        daily = await c.get("/v1/memory/daily-log", params={"user_id": "user_1"})
        people = await c.get("/v1/memory/people", params={"user_id": "user_1"})

    assert ingested.json()["status"] == "ingested"
    assert "whatsapp message from Alex" in daily.json()["content"]
    assert "YC application" in daily.json()["content"]
    assert "Alex appeared in whatsapp thread yc-prep." in people.json()["content"]


@pytest.mark.asyncio
async def test_messaging_bridge_respects_source_toggle(client):
    async with client as c:
        await c.put("/v1/memory/sources/whatsapp", json={
            "user_id": "user_1",
            "enabled": False,
            "reason": "pause chat learning",
        })
        ingested = await c.post("/v1/messaging/whatsapp/messages", json={
            "user_id": "user_1",
            "sender": "Alex",
            "text": "Do not remember this chat.",
        })
        daily = await c.get("/v1/memory/daily-log", params={"user_id": "user_1"})

    assert ingested.json()["status"] == "ingested"
    assert all(
        update["status"] == "skipped_source_disabled"
        for update in ingested.json()["memory_updates"]
    )
    assert "Do not remember this chat" not in daily.json()["content"]


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
    assert event.json()["event"]["metadata"] == {"raw_note": "email user@example.com"}
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


def test_google_connector_oauth_scopes_are_per_connector(monkeypatch):
    from pcl.oauth import start_oauth_flow

    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-google-client.apps.googleusercontent.com")
    expected = {
        "gmail": ["https://www.googleapis.com/auth/gmail.readonly"],
        "calendar": ["https://www.googleapis.com/auth/calendar.readonly"],
        "google_drive": ["https://www.googleapis.com/auth/drive.metadata.readonly"],
    }

    responses = {
        source: start_oauth_flow(
            source=source,
            user_id="user_1",
            redirect_uri="http://localhost/callback",
        )
        for source in expected
    }

    for source, response in responses.items():
        assert response["status"] == "ok"
        query = parse_qs(urlparse(response["auth_url"]).query)
        assert query["scope"][0].split() == expected[source]


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
