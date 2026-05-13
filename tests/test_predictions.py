import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


def test_predict_next_context_uses_llm_and_persona_signals(monkeypatch, tmp_path):
    import database
    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'predictions.db')
    database.create_tables()

    now = int(time.time() * 1000)
    database.insert_event(
        "https://github.com/modelcontextprotocol/python-sdk",
        "MCP Python SDK",
        "github.com",
        300,
        "build mcp server",
        now,
    )
    database.insert_feed_item(
        "claude_code",
        "session_signals",
        "[claude_code] task:building | domain:ai_ml | langs:python | tools:fastapi,mcp",
        "user",
        "session.jsonl",
        now,
    )

    from living_persona import record_browsing_signals, record_feed_signals
    from predictions import predict_next_context

    record_browsing_signals(
        url="https://github.com/modelcontextprotocol/python-sdk",
        title="MCP Python SDK for AI agents",
        time_spent_seconds=300,
        search_query="build mcp server",
        timestamp=now,
    )
    record_feed_signals(
        source="claude_code",
        content_type="session_signals",
        content="[claude_code] task:building | domain:ai_ml | langs:python | tools:fastapi,mcp",
        timestamp=now,
    )

    prediction = predict_next_context(days=7)

    assert prediction["prediction"]["next_task"] in {"building", "active_llm_work"}
    assert prediction["prediction"]["confidence"] > 0
    context_names = {item["name"] for item in prediction["prediction"]["needed_context"]}
    assert "current_goals" in context_names
    assert prediction["meta"]["model"] == "local_behavior_prediction_v1"


def test_mcp_predict_next_context(monkeypatch, tmp_path):
    import database
    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'mcp_predictions.db')
    database.create_tables()

    from mcp_server import handle_predict_next_context

    result = handle_predict_next_context(days=7)

    import json
    data = json.loads(result)
    assert "prediction" in data
    assert data["meta"]["data_window_days"] == 7
