# tests/test_mcp.py
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import json

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
