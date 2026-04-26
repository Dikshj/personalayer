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
