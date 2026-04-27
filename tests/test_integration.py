# tests/test_integration.py
"""
Integration test — full pipeline:
event ingestion -> SQLite -> persona extraction (mocked) -> MCP tools
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import json
import time
from unittest.mock import patch, MagicMock

MOCK_PERSONA = {
    "identity": {"role": "developer", "expertise": ["Python"], "current_project": "PersonaLayer"},
    "voice": {"style": "terse", "formality": "casual-professional", "emoji": False},
    "decisions": {"optimizes_for": "speed", "risk_tolerance": "high", "instant_yes": ["OSS"], "instant_no": []},
    "context": {"building": "MCP server", "blocked_on": "", "learning_this_week": ["MCP"], "active_hours": "22:00-02:00"},
    "interests": {"obsessions": ["AI agents"], "depth": {"expert": ["Python"], "learning": ["MCP"], "shallow": []}},
    "values": {"trusts": ["YC"], "dislikes": ["hype"]},
    "meta": {"updated_at": "2026-04-26T00:00:00", "data_window_days": 7, "event_count": 50}
}


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch, tmp_path):
    import database
    import persona
    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'integration.db')
    monkeypatch.setattr(persona, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(persona, 'PERSONA_FILE', tmp_path / 'persona.json')
    import main
    monkeypatch.setattr(main, 'create_scheduler',
                        lambda: MagicMock(start=lambda: None, shutdown=lambda: None))
    import database as db
    db.create_tables()


@pytest.mark.asyncio
async def test_full_pipeline(tmp_path):
    """Event ingested -> persona extracted -> MCP tools return data."""
    from httpx import AsyncClient
    from main import app
    from mcp_server import handle_get_persona, handle_get_context, handle_get_current_focus

    persona_file = str(tmp_path / 'persona.json')

    # 1. Ingest 5 browsing events
    async with AsyncClient(app=app, base_url="http://test") as client:
        for i in range(5):
            resp = await client.post("/event", json={
                "url": f"https://github.com/anthropics/repo{i}",
                "title": f"GitHub Repo {i}",
                "time_spent_seconds": 120,
                "timestamp": int(time.time() * 1000) - i * 60000,
            })
            assert resp.json()["status"] == "ok"

    # 2. Mock Claude and run extraction
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=json.dumps(MOCK_PERSONA))]

    with patch('persona.Anthropic') as mock_client:
        mock_client.return_value.messages.create.return_value = mock_resp
        from persona import extract_persona
        result = extract_persona()

    assert result["identity"]["role"] == "developer"

    # 3. Write persona file so MCP tools can read it
    (tmp_path / 'persona.json').write_text(json.dumps(MOCK_PERSONA))

    # 4. MCP tools read persona correctly
    persona_data = json.loads(handle_get_persona(persona_file))
    assert persona_data["identity"]["current_project"] == "PersonaLayer"

    ctx = json.loads(handle_get_context("python", persona_file))
    assert ctx["depth"] == "expert"

    focus = json.loads(handle_get_current_focus(persona_file))
    assert focus["building"] == "MCP server"


@pytest.mark.asyncio
async def test_health_and_persona_endpoints(tmp_path):
    """Server health + persona endpoint return correct shapes."""
    from httpx import AsyncClient
    from main import app

    async with AsyncClient(app=app, base_url="http://test") as client:
        health = await client.get("/health")
        assert health.json() == {"status": "ok", "service": "personalayer"}

        # No persona yet — should return error key
        persona_resp = await client.get("/persona")
        data = persona_resp.json()
        assert "error" in data
