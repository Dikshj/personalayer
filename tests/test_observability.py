import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


def test_observability_redacts_sensitive_attributes(monkeypatch, tmp_path):
    import database
    from pcl.observability import record_observability_event

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'observability.db')
    database.create_tables()

    event = record_observability_event(
        user_id="user_1",
        source="api",
        event_name="connector_sync_failed",
        severity="error",
        route="/pcl/integrations/gmail/sync",
        status_code=503,
        duration_ms=42,
        attributes={
            "account": "person@example.com",
            "access_token": "sk-testsecretvalue1234567890",
            "message": "retry for +1 555 123 4567",
        },
    )

    stored = database.list_observability_events("user_1")[0]
    text = str(stored).lower()

    assert event["event_hash"]
    assert stored["attributes"]["account"] == "[email]"
    assert "access_token" not in stored["attributes"]
    assert "[phone]" in stored["attributes"]["message"]
    assert "person@example.com" not in text
    assert "sk-testsecret" not in text


def test_observability_api_records_redacted_event(monkeypatch, tmp_path):
    import database
    from backend import app as _app

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'observability_api.db')

    with TestClient(_app) as client:
        response = client.post("/v1/observability/events", json={
            "user_id": "user_1",
            "source": "edge",
            "event_name": "request_complete",
            "attributes": {
                "email": "person@example.com",
                "refresh_token": "secret",
            },
        })

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "recorded"
    assert data["event"]["attributes"] == {"email": "[email]"}
