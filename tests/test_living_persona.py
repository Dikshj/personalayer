import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


def test_browsing_event_creates_living_persona_signals(monkeypatch, tmp_path):
    import database
    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'living.db')
    database.create_tables()

    from living_persona import build_living_persona, record_browsing_signals

    record_browsing_signals(
        url="https://github.com/modelcontextprotocol/python-sdk",
        title="MCP Python SDK for AI agents",
        time_spent_seconds=240,
        search_query="build mcp server for ai agents",
        timestamp=int(time.time() * 1000),
    )

    persona = build_living_persona()
    interest_names = {item["name"] for item in persona["interests"]}
    skill_names = {item["name"] for item in persona["skills"]}

    assert "ai_agents" in interest_names
    assert "python" in skill_names
    assert persona["meta"]["signal_count"] > 0


def test_context_contract_shares_only_allowed_context(monkeypatch, tmp_path):
    import database
    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'policy.db')
    database.create_tables()
    database.save_persona({
        "voice": {"style": "direct"},
        "context": {"building": "PersonalLayer"},
        "values": {"dislikes": ["generic spam"]},
        "identity": {"current_project": "PersonalLayer", "expertise": ["AI agents"]},
        "decisions": {"optimizes_for": "useful personalization", "risk_tolerance": "careful"},
    })

    from living_persona import record_feed_signals
    from policy import build_scoped_persona, negotiate_context_contract

    record_feed_signals(
        source="youtube",
        content_type="watch",
        content="MCP tutorial for AI agent platforms",
        timestamp=int(time.time() * 1000),
    )

    contract = negotiate_context_contract(
        platform_type="email_service",
        facilities=["inbox_prioritization", "reply_drafting"],
        requested_context=["communication_style", "priority_topics", "raw_email_content"],
        purpose="personalize inbox and replies",
    )

    scoped = build_scoped_persona(contract["contract_id"])

    assert "communication_style" in scoped["context"]
    assert "priority_topics" in scoped["context"]
    assert "raw_email_content" in contract["denied_context"]
    assert "raw_email_content" not in scoped["context"]


def test_persona_feedback_can_hide_wrong_signal(monkeypatch, tmp_path):
    import database
    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'feedback.db')
    database.create_tables()

    from living_persona import build_living_persona, record_feed_signals

    now = int(time.time() * 1000)
    record_feed_signals(
        source="youtube",
        content_type="watch",
        content="AI agents and MCP tutorial",
        timestamp=now,
    )

    before = build_living_persona()
    assert "ai_agents" in {item["name"] for item in before["interests"]}

    database.insert_persona_feedback(
        signal_type="interest",
        name="ai_agents",
        action="hide",
        reason="one-off watch",
    )

    after = build_living_persona()
    assert "ai_agents" not in {item["name"] for item in after["interests"]}


def test_revoked_context_contract_denies_future_access(monkeypatch, tmp_path):
    import database
    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'revoked.db')
    database.create_tables()
    database.save_persona({"voice": {"style": "direct"}})

    from policy import build_scoped_persona, negotiate_context_contract

    contract = negotiate_context_contract(
        platform_type="email_service",
        facilities=["reply_drafting"],
        requested_context=["communication_style"],
    )

    first = build_scoped_persona(contract["contract_id"])
    assert "communication_style" in first["context"]

    assert database.revoke_context_contract(contract["contract_id"]) is True
    second = build_scoped_persona(contract["contract_id"])
    assert second["error"] == "contract_revoked"

    logs = database.get_context_access_logs(contract["contract_id"])
    assert {log["action"] for log in logs} == {
        "scoped_persona_returned",
        "denied_revoked_contract",
    }
