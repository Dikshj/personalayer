# tests/test_mcp.py
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import json
import time

SAMPLE_PERSONA = {
    "identity": {"role": "developer", "expertise": ["Python", "MCP"], "current_project": "PersonaLayer"},
    "voice": {"style": "terse", "formality": "casual-professional", "emoji": False},
    "decisions": {"optimizes_for": "speed", "risk_tolerance": "high", "instant_yes": ["open source"], "instant_no": ["vendor lock-in"]},
    "context": {"building": "MCP server", "blocked_on": "persona schema", "learning_this_week": ["MCP protocol"], "active_hours": "22:00-02:00"},
    "interests": {"obsessions": ["AI agents", "YC"], "depth": {"expert": ["Python"], "learning": ["vector DBs", "MCP"], "shallow": ["mobile"]}},
    "values": {"trusts": ["YC", "OSS"], "dislikes": ["hype"]},
    "meta": {"updated_at": "2026-04-26T00:00:00", "data_window_days": 7, "event_count": 150}
}


@pytest.fixture
def persona_file(tmp_path):
    f = tmp_path / "persona.json"
    f.write_text(json.dumps(SAMPLE_PERSONA))
    return f


def test_get_persona_returns_full_profile(persona_file):
    from mcp_server import handle_get_persona
    result = handle_get_persona(str(persona_file))
    data = json.loads(result)
    assert data["identity"]["role"] == "developer"
    assert data["identity"]["current_project"] == "PersonaLayer"


def test_get_persona_no_file():
    from mcp_server import handle_get_persona
    result = handle_get_persona("/nonexistent/persona.json")
    data = json.loads(result)
    assert "error" in data


def test_get_context_known_topic(persona_file):
    from mcp_server import handle_get_context
    result = handle_get_context("mcp", str(persona_file))
    data = json.loads(result)
    assert data["depth"] == "learning"


def test_get_context_expert_topic(persona_file):
    from mcp_server import handle_get_context
    result = handle_get_context("python", str(persona_file))
    data = json.loads(result)
    assert data["depth"] == "expert"


def test_get_context_unknown_topic(persona_file):
    from mcp_server import handle_get_context
    result = handle_get_context("blockchain", str(persona_file))
    data = json.loads(result)
    assert data["depth"] == "unknown"


def test_get_current_focus(persona_file):
    from mcp_server import handle_get_current_focus
    result = handle_get_current_focus(str(persona_file))
    data = json.loads(result)
    assert data["building"] == "MCP server"
    assert "MCP protocol" in data["learning_this_week"]


def test_negotiate_context_contract(monkeypatch, tmp_path):
    import database
    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'mcp_policy.db')
    database.create_tables()

    from mcp_server import handle_negotiate_context
    result = handle_negotiate_context({
        "platform_type": "content_app",
        "facilities": ["content_recommendations"],
        "requested_context": ["priority_topics", "full_browsing_history"],
    })
    data = json.loads(result)

    assert "priority_topics" in data["granted_context"]
    assert "full_browsing_history" in data["denied_context"]


def test_mcp_revoke_context_contract(monkeypatch, tmp_path):
    import database
    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'mcp_revoke.db')
    database.create_tables()

    from mcp_server import handle_negotiate_context, handle_revoke_context_contract

    contract = json.loads(handle_negotiate_context({
        "platform_type": "content_app",
        "facilities": ["content_recommendations"],
    }))
    result = json.loads(handle_revoke_context_contract(contract["contract_id"]))

    assert result["status"] == "revoked"
    assert database.get_context_contract(contract["contract_id"])["status"] == "revoked"


def test_mcp_record_persona_feedback(monkeypatch, tmp_path):
    import database
    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'mcp_feedback.db')
    database.create_tables()

    from mcp_server import handle_record_persona_feedback

    result = json.loads(handle_record_persona_feedback({
        "signal_type": "interest",
        "name": "ai_agents",
        "action": "confirm",
        "reason": "core project",
    }))

    assert result["status"] == "ok"
    assert database.get_persona_feedback()[0]["action"] == "confirm"


def test_mcp_pcl_get_profile_uses_onboarding_seed(monkeypatch, tmp_path):
    import database
    from pcl.onboarding import build_onboarding_seed

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'mcp_pcl_profile.db')
    database.create_tables()
    database.save_pcl_onboarding_seed(
        "user_1",
        {"identity": "Founder, developer tools"},
        build_onboarding_seed({"identity": "Founder, developer tools"}),
    )

    from mcp_server import handle_pcl_get_profile
    data = json.loads(handle_pcl_get_profile("user_1"))

    assert data["identity"]["role"] == "Founder"
    assert data["identity"]["domain"] == "developer tools"


def test_mcp_pcl_get_feature_usage(monkeypatch, tmp_path):
    import database

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'mcp_pcl_usage.db')
    database.create_tables()
    database.insert_pcl_feature_event(
        app_id="app_1",
        user_id="user_1",
        feature_id="kanban",
        feature_name="Kanban",
        event_type="used",
        weight=1.0,
        metadata={},
        timestamp=int(time.time() * 1000),
    )

    from mcp_server import handle_pcl_get_feature_usage
    data = json.loads(handle_pcl_get_feature_usage({"user_id": "user_1"}))

    assert data["features"][0]["feature_id"] == "kanban"


def test_mcp_pcl_get_context_enforces_app_permissions(monkeypatch, tmp_path):
    import database

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'mcp_pcl_context.db')
    database.create_tables()
    database.register_pcl_app("mail_app", "Mail App", ["identity_role"])

    from mcp_server import handle_pcl_get_context
    data = json.loads(handle_pcl_get_context({
        "app_id": "mail_app",
        "user_id": "user_1",
        "requested_layers": ["identity_role", "capability_signals"],
        "features": [{"feature_id": "smart_reply", "name": "Smart Reply"}],
    }))

    assert data["allowed_layers"] == ["identity_role"]
    assert "capability_signals" not in data["context"]
    assert data["audit"]["log_id"]


def test_mcp_pcl_get_constraints(monkeypatch, tmp_path):
    import database
    from pcl.onboarding import build_onboarding_seed

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'mcp_pcl_constraints.db')
    database.create_tables()
    database.save_pcl_onboarding_seed(
        "user_1",
        {"preferences": "never show AI Summary"},
        build_onboarding_seed({"preferences": "never show AI Summary"}),
    )

    from mcp_server import handle_pcl_get_constraints
    data = json.loads(handle_pcl_get_constraints("user_1"))

    assert data["constraints"]["never show AI Summary"] is False


def test_mcp_contextlayer_bundle_active_context_and_feature_signals(monkeypatch, tmp_path):
    import database
    from pcl.contextlayer import ingest_context_event, update_active_context

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'mcp_contextlayer.db')
    database.create_tables()

    now_ms = int(time.time() * 1000)
    for _ in range(4):
        ingest_context_event(
            {
                "user_id": "user_1",
                "app_id": "figma",
                "feature_id": "auto-layout",
                "action": "used",
                "session_id": "s1",
                "timestamp": now_ms,
            },
            source="sdk",
        )
    update_active_context(
        user_id="user_1",
        project="Design system",
        active_apps=["figma"],
        inferred_intent="adapt_ui",
        session_depth="deep-work",
    )

    from mcp_server import (
        handle_contextlayer_get_active_context,
        handle_contextlayer_get_bundle,
        handle_contextlayer_get_feature_usage,
    )
    bundle = json.loads(handle_contextlayer_get_bundle({
        "user_id": "user_1",
        "app_id": "figma",
        "intent": "adapt_ui",
    }))
    active = json.loads(handle_contextlayer_get_active_context("user_1"))
    signals = json.loads(handle_contextlayer_get_feature_usage({
        "user_id": "user_1",
        "app_id": "figma",
    }))

    assert bundle["features"] == ["auto-layout"]
    assert bundle["permission"]["status"] == "local_default"
    assert active["active_context"]["project"] == "Design system"
    assert signals["features"][0]["feature_id"] == "auto-layout"
    assert signals["features"][0]["recency_score"] == 0.4


def test_mcp_contextlayer_tools_enforce_developer_auth_when_key_present(monkeypatch, tmp_path):
    import database
    from pcl.contextlayer import ingest_context_event, update_active_context

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'mcp_contextlayer_auth.db')
    database.create_tables()

    developer = database.upsert_developer("dev@example.com", "Dev")
    database.register_developer_app(developer["id"], "figma", "Figma")
    key = database.create_developer_api_key(developer["id"], app_id="figma")
    ingest_context_event(
        {
            "user_id": "user_1",
            "app_id": "figma",
            "feature_id": "auto-layout",
            "action": "used",
            "session_id": "s1",
            "timestamp": int(time.time() * 1000),
        },
        source="sdk",
    )
    update_active_context("user_1", project="Design system", active_apps=["figma"])

    from mcp_server import (
        handle_contextlayer_get_active_context,
        handle_contextlayer_get_bundle,
        handle_contextlayer_get_constraints,
        handle_contextlayer_get_feature_usage,
    )

    denied = json.loads(handle_contextlayer_get_bundle({
        "app_id": "figma",
        "developer_api_key": key["key"],
        "user_token": "user:user_1",
        "requested_scopes": ["getFeatureUsage"],
    }))
    database.grant_app_consent(
        "user_1",
        "figma",
        scopes=["getFeatureUsage", "getActiveContext", "getConstraints"],
        developer_id=developer["id"],
    )
    bundle = json.loads(handle_contextlayer_get_bundle({
        "app_id": "figma",
        "developer_api_key": key["key"],
        "user_token": "user:user_1",
        "intent": "adapt_ui",
        "requested_scopes": ["getFeatureUsage"],
    }))
    signals = json.loads(handle_contextlayer_get_feature_usage({
        "app_id": "figma",
        "developer_api_key": key["key"],
        "user_token": "user:user_1",
    }))
    active = json.loads(handle_contextlayer_get_active_context({
        "app_id": "figma",
        "developer_api_key": key["key"],
        "user_token": "user:user_1",
    }))
    constraints = json.loads(handle_contextlayer_get_constraints({
        "app_id": "figma",
        "developer_api_key": key["key"],
        "user_token": "user:user_1",
    }))

    assert denied["error"] == "missing_user_consent"
    assert bundle["auth"]["mode"] == "developer"
    assert bundle["permission"]["status"] == "granted"
    assert signals["auth"]["mode"] == "developer"
    assert signals["features"][0]["feature_id"] == "auto-layout"
    assert active["active_context"]["project"] == "Design system"
    assert constraints["auth"]["mode"] == "developer"


def test_mcp_contextlayer_tools_reject_missing_scope(monkeypatch, tmp_path):
    import database

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'mcp_contextlayer_scope.db')
    database.create_tables()

    developer = database.upsert_developer("dev@example.com", "Dev")
    database.register_developer_app(developer["id"], "figma", "Figma")
    key = database.create_developer_api_key(developer["id"], app_id="figma")
    database.grant_app_consent(
        "user_1",
        "figma",
        scopes=["getFeatureUsage"],
        developer_id=developer["id"],
    )

    from mcp_server import handle_contextlayer_get_constraints

    denied = json.loads(handle_contextlayer_get_constraints({
        "app_id": "figma",
        "developer_api_key": key["key"],
        "user_token": "user:user_1",
    }))

    assert denied["error"] == "scope_not_granted"
