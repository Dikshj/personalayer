# tests/test_persona.py
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import json
from pathlib import Path
from unittest.mock import patch, MagicMock


def make_events(n=20):
    import time
    now = int(time.time() * 1000)
    return [
        {
            "id": i,
            "url": f"https://github.com/page{i}",
            "title": f"GitHub Page {i}",
            "domain": "github.com",
            "time_spent_seconds": 120,
            "search_query": "mcp python" if i % 3 == 0 else None,
            "timestamp": now - i * 60000,
        }
        for i in range(n)
    ]


@pytest.fixture(autouse=True)
def use_test_paths(monkeypatch, tmp_path):
    import persona as p
    monkeypatch.setattr(p, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(p, 'PERSONA_FILE', tmp_path / 'persona.json')
    # Mock save_persona to avoid database calls in persona tests
    monkeypatch.setattr('persona.save_persona', lambda x: None)


def test_summarize_events_top_domains():
    from persona import summarize_events
    events = make_events(10)
    summary = summarize_events(events)
    assert "github.com" in summary
    assert "TOP DOMAINS" in summary


def test_summarize_events_includes_searches():
    from persona import summarize_events
    events = make_events(10)
    summary = summarize_events(events)
    assert "mcp python" in summary


def test_summarize_events_empty():
    from persona import summarize_events
    result = summarize_events([])
    assert result == ""


def test_extract_persona_writes_file(tmp_path):
    from persona import extract_persona

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({
        "identity": {"role": "developer", "expertise": ["Python"], "current_project": "PersonaLayer"},
        "voice": {"style": "terse", "formality": "casual-professional", "emoji": False},
        "decisions": {"optimizes_for": "speed", "risk_tolerance": "high", "instant_yes": ["open source"], "instant_no": ["vendor lock-in"]},
        "context": {"building": "MCP server", "blocked_on": "", "learning_this_week": ["MCP"], "active_hours": "22:00-02:00"},
        "interests": {"obsessions": ["AI agents"], "depth": {"expert": ["Python"], "learning": ["MCP"], "shallow": []}},
        "values": {"trusts": ["YC companies"], "dislikes": ["hype"]},
        "meta": {"updated_at": "2026-04-26T00:00:00", "data_window_days": 7, "event_count": 20}
    }))]

    with patch('persona.get_events_last_n_days', return_value=make_events(20)), \
         patch('persona.Anthropic') as mock_anthropic:
        mock_anthropic.return_value.messages.create.return_value = mock_response
        result = extract_persona()

    assert result["identity"]["role"] == "developer"
    persona_file = tmp_path / 'persona.json'
    assert persona_file.exists()
    saved = json.loads(persona_file.read_text())
    assert saved["identity"]["role"] == "developer"


def test_extract_persona_returns_empty_when_no_events():
    from persona import extract_persona
    with patch('persona.get_events_last_n_days', return_value=[]):
        result = extract_persona()
    assert result == {}
