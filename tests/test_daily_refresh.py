import os
import sys
import time
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


@pytest.fixture(autouse=True)
def use_test_db(monkeypatch, tmp_path):
    import database

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'daily_refresh.db')
    database.create_tables()


def test_daily_refresh_runs_all_steps_and_writes_profile_fields():
    import database
    from pcl.contextlayer import build_context_bundle, ingest_context_event
    from pcl.daily_refresh import run_daily_refresh

    now_ms = int(time.time() * 1000)
    for index in range(30):
        ingest_context_event(
            {
                "user_id": "user_1",
                "app_id": "figma",
                "feature_id": "auto-layout",
                "action": "used",
                "session_id": f"s{index % 5}",
                "timestamp": now_ms,
            },
            source="extension",
        )

    before = build_context_bundle("user_1", "figma", intent="full_profile")
    result = run_daily_refresh("user_1", timezone="Asia/Calcutta", today=datetime(2026, 5, 13))
    profile = database.get_user_profile_record("user_1")
    signal = database.get_feature_signal("user_1", "figma", "auto-layout")
    after = build_context_bundle("user_1", "figma", intent="full_profile")

    assert before["stale"] is True
    assert result["status"] == "complete"
    assert result["job"]["step_completed"] == 11
    assert [log["step_number"] for log in result["logs"]] == list(range(1, 12))
    assert profile["last_synthesized_at"] is not None
    assert profile["context_brief"]
    assert profile["daily_insight"]
    assert signal["tier"] == "core"
    assert after["stale"] is False


def test_daily_refresh_can_resume_from_completed_step():
    from pcl.contextlayer import ingest_context_event
    from pcl.daily_refresh import run_daily_refresh

    ingest_context_event(
        {
            "user_id": "user_1",
            "app_id": "notion",
            "feature_id": "database-view",
            "action": "used",
            "session_id": "s1",
            "timestamp": int(time.time() * 1000),
        },
        source="sdk",
    )

    result = run_daily_refresh(
        "user_1",
        timezone="UTC",
        job_id="resume-job",
        step_completed=5,
        today=datetime(2026, 5, 13),
    )

    assert result["status"] == "complete"
    assert result["job"]["id"] == "resume-job"
    assert [log["step_number"] for log in result["logs"]] == [6, 7, 8, 9, 10, 11]


def test_daily_refresh_due_selection_uses_user_local_timezone():
    import database
    from pcl.daily_refresh import is_daily_refresh_due, run_due_daily_refreshes

    database.update_user_profile_record("india_user", timezone="Asia/Calcutta")
    database.update_user_profile_record("utc_user", timezone="UTC")

    now = datetime(2026, 5, 12, 22, 0, tzinfo=timezone.utc)

    india_profile = database.get_user_profile_record("india_user")
    utc_profile = database.get_user_profile_record("utc_user")
    assert is_daily_refresh_due(india_profile, now) is True
    assert is_daily_refresh_due(utc_profile, now) is True

    result = run_due_daily_refreshes(now=now)

    assert result["status"] == "ok"
    assert set(result["due_users"]) == {"india_user", "utc_user"}
    assert database.get_user_profile_record("india_user")["last_refresh_at"] is not None
    assert database.get_user_profile_record("utc_user")["last_refresh_at"] is not None


def test_daily_refresh_not_due_before_3am_local_after_same_day_refresh():
    import database
    from pcl.daily_refresh import is_daily_refresh_due

    refreshed_at = int(datetime(2026, 5, 12, 22, 0, tzinfo=timezone.utc).timestamp() * 1000)
    database.update_user_profile_record(
        "user_1",
        timezone="Asia/Calcutta",
        last_refresh_at=refreshed_at,
    )
    profile = database.get_user_profile_record("user_1")

    assert is_daily_refresh_due(
        profile,
        datetime(2026, 5, 12, 22, 30, tzinfo=timezone.utc),
    ) is False


def test_monthly_refresh_runs_tsubasa_step():
    import database
    from pcl.contextlayer import ingest_context_event
    from pcl.daily_refresh import run_daily_refresh

    now_ms = int(time.time() * 1000)
    for index in range(10):
        ingest_context_event(
            {
                "user_id": "user_1",
                "app_id": "app",
                "feature_id": f"feature-{index}",
                "action": "used",
                "session_id": f"s{index}",
                "timestamp": now_ms,
            },
            source="sdk",
        )

    result = run_daily_refresh("user_1", today=datetime(2026, 6, 1))
    profile = database.get_user_profile_record("user_1")

    assert result["status"] == "complete"
    assert any(
        attr["attribute"] == "long-horizon-tool-pattern"
        for attr in profile["abstract_attributes"]
    )


@pytest.mark.asyncio
async def test_daily_refresh_endpoint(client):
    async with client as c:
        await c.post("/v1/ingest/sdk", json={
            "user_id": "user_1",
            "app_id": "gmail",
            "feature_id": "smart-reply",
            "action": "used",
            "session_id": "s1",
            "timestamp": int(time.time() * 1000),
        })
        response = await c.post("/v1/jobs/daily-refresh", json={
            "user_id": "user_1",
            "timezone": "Asia/Calcutta",
        })

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "complete"
    assert data["job"]["timezone"] == "Asia/Calcutta"


@pytest.mark.asyncio
async def test_daily_refresh_status_due_and_brief_endpoints(client):
    async with client as c:
        await c.post("/v1/ingest/sdk", json={
            "user_id": "user_1",
            "app_id": "gmail",
            "feature_id": "smart-reply",
            "action": "used",
            "session_id": "s1",
            "timestamp": int(time.time() * 1000),
        })
        due = await c.post("/v1/jobs/daily-refresh/due", json={
            "now": "2026-05-13T04:00:00+00:00",
        })
        jobs = await c.get("/v1/jobs/daily-refresh", params={"user_id": "user_1"})
        brief = await c.get("/v1/context/brief", params={"user_id": "user_1"})

    due_data = due.json()
    brief_data = brief.json()
    assert due.status_code == 200
    assert due_data["refreshed"] == 1
    assert jobs.json()["jobs"][0]["status"] == "complete"
    assert brief_data["context_brief"]
    assert brief_data["daily_insight"]


@pytest.fixture
def client():
    from httpx import AsyncClient
    from main import app

    return AsyncClient(app=app, base_url="http://test")
