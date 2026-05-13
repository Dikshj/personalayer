import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


@pytest.fixture(autouse=True)
def use_test_db(monkeypatch, tmp_path):
    import database

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'contextlayer.db')
    database.create_tables()


def test_strict_context_event_drops_content_and_pii():
    import database
    from pcl.contextlayer import ingest_context_event

    dropped = ingest_context_event(
        {
            "user_id": "user_1",
            "app_id": "notion",
            "feature_id": "database-view",
            "action": "used",
            "timestamp": int(time.time() * 1000),
            "content": "email me at user@example.com",
        },
        source="sdk",
    )

    assert dropped["status"] == "dropped"
    assert dropped["reason"] == "unknown_fields:content"
    assert database.list_raw_context_events("user_1") == []
    assert database.list_privacy_filter_drops()[0]["reason"] == "unknown_fields:content"


def test_ingest_context_event_updates_feature_signal():
    import database
    from pcl.contextlayer import ingest_context_event

    result = ingest_context_event(
        {
            "user_id": "user_1",
            "app_id": "notion",
            "feature_id": "database-view",
            "action": "used",
            "session_id": "s1",
            "timestamp": int(time.time() * 1000),
        },
        source="extension",
    )

    signal = database.get_feature_signal("user_1", "notion", "database-view")
    assert result["status"] == "ok"
    assert signal["namespace"] == "notion:database-view"
    assert signal["usage_count"] == 1
    assert signal["tier"] == "episodic"
    assert signal["recency_score"] == 0.1


def test_context_bundle_uses_intent_boundary():
    from pcl.contextlayer import build_context_bundle, ingest_context_event

    now_ms = int(time.time() * 1000)
    for _ in range(4):
        ingest_context_event(
            {
                "user_id": "user_1",
                "app_id": "figma",
                "feature_id": "auto-layout",
                "action": "used",
                "timestamp": now_ms,
            },
            source="extension",
        )
    for _ in range(2):
        ingest_context_event(
            {
                "user_id": "user_1",
                "app_id": "figma",
                "feature_id": "dev-mode",
                "action": "used",
                "timestamp": now_ms,
            },
            source="extension",
        )

    adapt = build_context_bundle("user_1", "figma", intent="adapt_ui")
    full = build_context_bundle("user_1", "figma", intent="full_profile")

    assert adapt["features"] == ["auto-layout"]
    assert "dev-mode" not in adapt["features"]
    assert set(full["features"]) == {"auto-layout", "dev-mode"}
    assert full["active_context"] is not None


def test_stale_context_bundle_queues_urgent_synthesis():
    import database
    from pcl.contextlayer import build_context_bundle, ingest_context_event

    ingest_context_event(
        {
            "user_id": "user_1",
            "app_id": "figma",
            "feature_id": "auto-layout",
            "action": "used",
            "timestamp": int(time.time() * 1000),
        },
        source="extension",
    )

    bundle = build_context_bundle("user_1", "figma", intent="full_profile")
    jobs = database.list_daily_refresh_jobs(user_id="user_1")

    assert bundle["stale"] is True
    assert bundle["urgent_synthesis_job_id"]
    assert jobs[0]["id"] == bundle["urgent_synthesis_job_id"]


def test_context_feedback_applies_bandit_update():
    import database
    from pcl.contextlayer import apply_context_feedback, build_context_bundle, ingest_context_event

    now_ms = int(time.time() * 1000)
    for feature_id in ("smart-reply", "newsletter-filter"):
        for _ in range(4):
            ingest_context_event(
                {
                    "user_id": "user_1",
                    "app_id": "gmail",
                    "feature_id": feature_id,
                    "action": "used",
                    "timestamp": now_ms,
                },
                source="sdk",
            )
    bundle = build_context_bundle("user_1", "gmail", intent="adapt_ui")
    before_used = database.get_feature_signal("user_1", "gmail", "smart-reply")["recency_score"]
    before_unused = database.get_feature_signal("user_1", "gmail", "newsletter-filter")["recency_score"]

    result = apply_context_feedback(
        user_id="user_1",
        bundle_id=bundle["bundle_id"],
        app_id="gmail",
        outcome="accepted",
        features_actually_used=["smart-reply"],
    )

    after_used = database.get_feature_signal("user_1", "gmail", "smart-reply")["recency_score"]
    after_unused = database.get_feature_signal("user_1", "gmail", "newsletter-filter")["recency_score"]
    assert result["status"] == "ok"
    assert round(after_used - before_used, 2) == 0.05
    assert round(before_unused - after_unused, 2) == 0.01


def test_memory_jobs_promote_demote_and_decay(monkeypatch):
    import database
    from pcl.contextlayer import (
        ingest_context_event,
        run_decay_engine,
        run_inductive_memory_job,
        run_reflective_memory_job,
    )

    now_ms = int(time.time() * 1000)
    for index in range(30):
        ingest_context_event(
            {
                "user_id": "user_1",
                "app_id": "linear",
                "feature_id": "roadmap",
                "action": "used",
                "session_id": f"s{index % 5}",
                "timestamp": now_ms,
            },
            source="sdk",
        )
    promoted = run_inductive_memory_job()
    assert promoted["promoted"] == 1
    assert database.get_feature_signal("user_1", "linear", "roadmap")["tier"] == "core"

    stale_ms = now_ms + (91 * 24 * 60 * 60 * 1000)
    demoted = run_reflective_memory_job()
    assert demoted["demoted"] == 0
    demoted = database.demote_stale_core_feature_signals(now_ms=stale_ms)
    assert demoted == 1
    assert database.get_feature_signal("user_1", "linear", "roadmap")["tier"] == "episodic"

    decayed = run_decay_engine(now_ms=now_ms + (60 * 24 * 60 * 60 * 1000))
    assert decayed["updated"] >= 0


def test_single_session_burst_does_not_promote_to_core():
    import database
    from pcl.contextlayer import ingest_context_event, run_inductive_memory_job

    now_ms = int(time.time() * 1000)
    for _ in range(30):
        ingest_context_event(
            {
                "user_id": "user_1",
                "app_id": "linear",
                "feature_id": "views",
                "action": "used",
                "session_id": "single-session",
                "timestamp": now_ms,
            },
            source="sdk",
        )

    promoted = run_inductive_memory_job()

    assert promoted["promoted"] == 0
    assert database.get_feature_signal("user_1", "linear", "views")["tier"] == "episodic"


def test_active_context_activity_and_hard_delete():
    import database
    from pcl.contextlayer import (
        build_context_bundle,
        get_contextlayer_activity,
        hard_delete_contextlayer_user,
        ingest_context_event,
        update_active_context,
    )

    now_ms = int(time.time() * 1000)
    ingest_context_event(
        {
            "user_id": "user_1",
            "app_id": "figma",
            "feature_id": "auto-layout",
            "action": "used",
            "timestamp": now_ms,
        },
        source="extension",
    )
    ingest_context_event(
        {
            "user_id": "user_1",
            "app_id": "figma",
            "feature_id": "private-note",
            "action": "used",
            "timestamp": now_ms,
            "content": "private",
        },
        source="extension",
    )
    heartbeat = update_active_context(
        user_id="user_1",
        project="ContextLayer",
        active_apps=["figma"],
        inferred_intent="adapt_ui",
        session_depth="deep-work",
    )
    bundle = build_context_bundle("user_1", "figma", intent="full_profile")
    activity = get_contextlayer_activity("user_1")

    assert heartbeat["active_context"]["project"] == "ContextLayer"
    assert bundle["active_context"]["project"] == "ContextLayer"
    assert activity["raw_events"][0]["feature_id"] == "auto-layout"
    assert activity["query_log"][0]["app_id"] == "figma"

    deleted = hard_delete_contextlayer_user("user_1")

    assert deleted["status"] == "deleted"
    assert database.list_raw_context_events("user_1") == []
    assert database.list_feature_signals("user_1") == []
    assert database.list_privacy_filter_drops(user_id="user_1") == []
    assert database.get_active_context("user_1") is None


@pytest.mark.asyncio
async def test_feature_signals_endpoint(client):
    async with client as c:
        await c.post("/v1/ingest/sdk", json={
            "user_id": "user_1",
            "app_id": "figma",
            "feature_id": "components",
            "action": "used",
            "timestamp": int(time.time() * 1000),
        })
        response = await c.get("/v1/context/feature-signals", params={
            "user_id": "user_1",
            "app_id": "figma",
        })

    data = response.json()
    assert response.status_code == 200
    assert data["features"][0]["feature_id"] == "components"


@pytest.mark.asyncio
async def test_privacy_drops_and_raw_cleanup_endpoints(client):
    import database

    now_ms = int(time.time() * 1000)
    old_ms = now_ms - (8 * 24 * 60 * 60 * 1000)
    async with client as c:
        await c.post("/v1/ingest/sdk", json={
            "user_id": "user_1",
            "app_id": "notion",
            "feature_id": "database-view",
            "action": "used",
            "timestamp": now_ms,
        })
        with database.get_connection() as conn:
            conn.execute(
                "UPDATE raw_events SET created_at = ? WHERE user_id = ?",
                (old_ms, "user_1"),
            )
            conn.commit()
        await c.post("/v1/ingest/sdk", json={
            "user_id": "user_1",
            "app_id": "notion",
            "feature_id": "private-note",
            "action": "used",
            "timestamp": now_ms,
            "content": "secret",
        })
        drops = await c.get("/v1/context/privacy-drops", params={"user_id": "user_1"})
        cleanup = await c.post("/v1/context/raw-events/cleanup", json={
            "user_id": "user_1",
            "older_than_days": 7,
        })

    assert drops.status_code == 200
    assert drops.json()["drops"][0]["reason"] == "unknown_fields:content"
    assert cleanup.json()["deleted"] == 1


@pytest.fixture
def client():
    from httpx import AsyncClient
    from main import app

    return AsyncClient(app=app, base_url="http://test")
