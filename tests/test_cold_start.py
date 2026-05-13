import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


@pytest.fixture(autouse=True)
def use_test_db(monkeypatch, tmp_path):
    import database

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'cold_start.db')
    database.create_tables()


def test_context_event_accepts_whitelisted_metadata():
    import database
    from pcl.contextlayer import ingest_context_event

    result = ingest_context_event(
        {
            "user_id": "user_1",
            "app_id": "zomato",
            "feature_id": "food-order",
            "action": "used",
            "timestamp": 1700000000000,
            "metadata": {
                "hour_of_day": 13,
                "day_of_week": 2,
                "subject_category": "lunch orders",
            },
        },
        source="sdk",
    )

    events = database.list_raw_context_events("user_1", days=3650)
    assert result["status"] == "ok"
    assert events[0]["metadata"] == {
        "hour_of_day": 13,
        "day_of_week": 2,
        "subject_category": "lunch-orders",
    }


def test_context_event_drops_unknown_metadata_fields():
    import database
    from pcl.contextlayer import ingest_context_event

    result = ingest_context_event(
        {
            "user_id": "user_1",
            "app_id": "gmail",
            "feature_id": "search",
            "action": "searched",
            "metadata": {"raw_subject": "private message"},
        },
        source="sdk",
    )

    assert result["status"] == "dropped"
    assert result["reason"] == "unknown_metadata_fields:raw_subject"
    assert database.list_raw_context_events("user_1") == []


def test_cold_start_generates_synthetic_low_confidence_signals():
    import database
    from pcl.cold_start import generate_cold_start_signals

    result = generate_cold_start_signals(
        user_id="user_1",
        app_id="figma",
        app_name="Figma",
        features=["Auto layout", "Components"],
        role="designer",
        domain="product design",
    )

    signals = database.list_feature_signals("user_1", app_id="figma")
    profile = database.get_user_profile_record("user_1")

    assert result["status"] == "ok"
    assert result["signals_created"] == 2
    assert {signal["feature_id"] for signal in signals} == {"auto-layout", "components"}
    assert all(signal["is_synthetic"] for signal in signals)
    assert all(signal["recency_score"] == 0.3 for signal in signals)
    assert profile["abstract_attributes"][0]["attribute"] == "cold-start-profile"


def test_cold_start_skips_when_real_signals_exist():
    from pcl.cold_start import generate_cold_start_signals
    from pcl.contextlayer import ingest_context_event

    ingest_context_event(
        {
            "user_id": "user_1",
            "app_id": "figma",
            "feature_id": "auto-layout",
            "action": "used",
        },
        source="sdk",
    )

    result = generate_cold_start_signals("user_1", "figma", role="designer")

    assert result["status"] == "skipped"
    assert result["reason"] == "existing_signals"


@pytest.mark.asyncio
async def test_cold_start_endpoint(client):
    async with client as c:
        response = await c.post("/v1/context/cold-start", json={
            "user_id": "user_1",
            "app_id": "github",
            "role": "engineer",
            "domain": "developer tools",
        })

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "ok"
    assert data["signals_created"] > 0


@pytest.mark.asyncio
async def test_ingest_endpoint_preserves_whitelisted_metadata(client):
    import database

    async with client as c:
        response = await c.post("/v1/ingest/sdk", json={
            "user_id": "user_1",
            "app_id": "figma",
            "feature_id": "components",
            "action": "used",
            "metadata": {
                "hour_of_day": 9,
                "day_of_week": 1,
                "subject_category": "design system",
            },
        })

    events = database.list_raw_context_events("user_1")
    assert response.json()["status"] == "ok"
    assert events[0]["metadata"] == {
        "hour_of_day": 9,
        "day_of_week": 1,
        "subject_category": "design-system",
    }


@pytest.fixture
def client():
    from httpx import AsyncClient
    from main import app

    return AsyncClient(app=app, base_url="http://test")
