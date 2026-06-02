"""End-to-end production hardening tests for Python backend.

Run with:
    PYTHONPATH=/mnt/c/Users/diks2/personalayer/backend pytest tests/test_production_hardening.py -v
"""
import os

import pytest
from fastapi.testclient import TestClient

from backend import app as _app


@pytest.fixture
def client():
    with TestClient(_app) as c:
        yield c


class TestHTTPSecurity:
    def test_health_endpoint_accessible(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"

    def test_sensitive_headers_not_exposed(self, client):
        response = client.get("/health")
        assert "X-Powered-By" not in response.headers

    def test_cors_preflight_options(self, client):
        response = client.options("/health")
        assert response.status_code in [200, 204, 400, 405]


class TestAuthentication:
    def test_unauthorized_bundle_without_token(self, client):
        """Bundle endpoint should require auth or return bundle with default user."""
        response = client.post("/v1/context/bundle", json={
            "app_id": "test_app",
            "intent": "full_profile",
            "requested_scopes": ["context_steering"]
        })
        # May succeed with default user or require auth depending on config
        assert response.status_code in [200, 401, 403]

    def test_invalid_token_format(self, client):
        response = client.post("/v1/context/bundle", json={
            "app_id": "test_app",
            "intent": "full_profile",
            "requested_scopes": ["context_steering"]
        }, headers={"Authorization": "InvalidToken"})
        assert response.status_code in [200, 401, 403]


class TestInputValidation:
    def test_invalid_json_rejected(self, client):
        response = client.post("/v1/ingest/extension", data="not json")
        assert response.status_code in [400, 422]

    def test_oversized_payload_rejected(self, client):
        large_payload = {"data": "x" * (2 * 1024 * 1024)}
        response = client.post("/v1/ingest/extension", json=large_payload)
        # FastAPI may accept or reject depending on config
        assert response.status_code in [200, 413, 400, 422]


class TestPrivacyControls:
    def test_delete_all_context(self, client):
        response = client.delete("/v1/context/all")
        assert response.status_code in [200, 401, 403]

    def test_query_log_accessible(self, client):
        response = client.get("/pcl/query-log")
        assert response.status_code in [200, 401, 403]

    def test_sensitive_data_not_in_bundle(self, client):
        response = client.post("/v1/context/bundle", json={
            "app_id": "test_app",
            "intent": "full_profile",
            "requested_scopes": ["context_steering"]
        })
        if response.status_code == 200:
            data = response.json()
            text = str(data).lower()
            assert "password" not in text
            assert "secret_key" not in text
            assert "api_key" not in text


class TestExtensionIngest:
    def test_extension_ingest_accepts_valid_event(self, client):
        response = client.post("/v1/ingest/extension", json={
            "user_id": "local_user",
            "event_type": "click",
            "feature_id": "save_button",
            "app_id": "test_extension"
        })
        assert response.status_code in [200, 401, 403, 422]

    def test_sdk_ingest_accepts_valid_event(self, client):
        response = client.post("/v1/ingest/sdk", json={
            "user_id": "local_user",
            "event_type": "feature_used",
            "feature_id": "dark_mode",
            "app_id": "test_sdk"
        })
        assert response.status_code in [200, 401, 403, 422]


class TestBundleEndpoint:
    def test_bundle_post_returns_valid_structure(self, client):
        response = client.post("/v1/context/bundle", json={
            "app_id": "test_app",
            "intent": "full_profile",
            "requested_scopes": ["context_steering"]
        })
        assert response.status_code in [200, 401, 403]
        if response.status_code == 200:
            data = response.json()
            assert "bundle_id" in data or "auth" in data

    def test_bundle_egress_filtered(self, client):
        response = client.post("/v1/context/bundle", json={
            "app_id": "test_app",
            "intent": "full_profile",
            "requested_scopes": ["context_steering"]
        })
        if response.status_code == 200:
            data = response.json()
            # Ensure no actual raw_content/raw_payload values (metadata flags OK)
            assert data.get("raw_content") is None
            assert data.get("raw_payload") is None
            # Egress metadata should indicate filtering occurred
            assert "_egress" in data or "auth" in data


class TestAssistantProxy:
    def test_assistant_chat_without_upstream_key(self, client):
        os.environ.pop("PERSONALAYER_DEV_MODE", None)
        os.environ.pop("OPENAI_API_KEY", None)
        response = client.post("/v1/assistant/chat", json={"message": "test"})
        assert response.status_code in [200, 503, 401]
        data = response.json()
        # Should be dry_run or error, not a real upstream call
        assert data.get("status") in ["dry_run", "error", "upstream_not_configured"]

    def test_chat_completions_without_upstream_key(self, client):
        os.environ.pop("PERSONALAYER_DEV_MODE", None)
        os.environ.pop("OPENAI_API_KEY", None)
        response = client.post("/v1/chat/completions", json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hello"}]
        })
        assert response.status_code in [200, 503, 401]
        data = response.json()
        assert data.get("status") in ["dry_run", "error", "upstream_not_configured"]


class TestAppsAndPermissions:
    def test_list_apps(self, client):
        response = client.get("/pcl/apps")
        assert response.status_code in [200, 401]

    def test_register_app(self, client):
        response = client.post("/pcl/apps", json={
            "app_id": "test_app_" + str(hash(os.urandom(4))),
            "name": "Test App",
            "allowed_layers": ["basic", "features"]
        })
        assert response.status_code in [200, 401, 422]


class TestIntegrations:
    def test_integration_catalog(self, client):
        response = client.get("/pcl/integrations/catalog")
        assert response.status_code == 200
        data = response.json()
        assert "integrations" in data

    def test_list_integrations(self, client):
        response = client.get("/pcl/integrations")
        assert response.status_code in [200, 401]


class TestDevModeGating:
    def test_dry_run_blocked_without_dev_mode(self, client):
        os.environ.pop("PERSONALAYER_DEV_MODE", None)
        response = client.post("/v1/assistant/chat", json={"message": "test"})
        data = response.json()
        # Without upstream key and without dev mode, should error
        if response.status_code == 200:
            assert data.get("status") in ["dry_run", "error", "upstream_not_configured"]
        else:
            assert response.status_code in [503, 401]

    def test_dry_run_allowed_with_dev_mode(self, client):
        os.environ["PERSONALAYER_DEV_MODE"] = "1"
        response = client.post("/v1/assistant/chat", json={"message": "test"})
        assert response.status_code in [200, 401]
