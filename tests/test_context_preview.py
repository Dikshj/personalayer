import pytest
from database import create_tables, insert_privacy_boundary
from pcl.context_preview import (
    generate_context_preview,
    handle_preview_decision,
    get_preview_history,
    _is_blocked_by_boundary,
    _build_plain_english_summary,
)
from pcl.models import ContextLayer


@pytest.fixture(autouse=True)
def _reset_db(tmp_path, monkeypatch):
    import database
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    database.create_tables()
    yield


class TestContextPreview:
    def test_generate_preview_basic(self):
        preview = generate_context_preview(
            user_id="test_user",
            app_id="demo-app",
            app_name="Demo App",
            requested_purpose="personalize UI",
            requested_layers=["identity_role"],
            requested_scopes=["ui"],
        )
        assert preview["id"]
        assert preview["user_id"] == "test_user"
        assert preview["app_id"] == "demo-app"
        assert preview["status"] == "pending"
        assert preview["plain_english_summary"]
        assert "allowed_fields" in preview

    def test_preview_with_blocked_layer(self):
        insert_privacy_boundary("test_user", "never_share_field", "identity_role", "private")
        preview = generate_context_preview(
            user_id="test_user",
            app_id="demo-app",
            app_name="Demo App",
            requested_purpose="test",
            requested_layers=["identity_role", "capability_signals"],
            requested_scopes=["ui"],
        )
        assert "identity_role" in preview["excluded_fields"]

    def test_preview_decision_approve(self):
        preview = generate_context_preview(
            user_id="test_user",
            app_id="demo-app",
            app_name="Demo App",
            requested_purpose="test",
            requested_layers=["capability_signals"],
            requested_scopes=["ui"],
        )
        result = handle_preview_decision(preview["id"], "approved")
        assert result["status"] == "approved"

    def test_preview_decision_deny(self):
        preview = generate_context_preview(
            user_id="test_user",
            app_id="demo-app",
            app_name="Demo App",
            requested_purpose="test",
            requested_layers=["capability_signals"],
            requested_scopes=["ui"],
        )
        result = handle_preview_decision(preview["id"], "denied")
        assert result["status"] == "denied"

    def test_preview_already_decided(self):
        preview = generate_context_preview(
            user_id="test_user",
            app_id="demo-app",
            app_name="Demo App",
            requested_purpose="test",
            requested_layers=["capability_signals"],
            requested_scopes=["ui"],
        )
        handle_preview_decision(preview["id"], "approved")
        result = handle_preview_decision(preview["id"], "denied")
        assert "error" in result

    def test_preview_history(self):
        generate_context_preview(
            user_id="test_user",
            app_id="app1",
            app_name="App 1",
            requested_purpose="test",
            requested_layers=["capability_signals"],
            requested_scopes=["ui"],
        )
        generate_context_preview(
            user_id="test_user",
            app_id="app2",
            app_name="App 2",
            requested_purpose="test2",
            requested_layers=["behavior_patterns"],
            requested_scopes=["ui"],
        )
        history = get_preview_history("test_user")
        assert history["count"] == 2


class TestHelpers:
    def test_is_blocked_by_boundary(self):
        boundaries = [{"boundary_type": "never_share_field", "target": "identity_role"}]
        assert _is_blocked_by_boundary("identity_role", boundaries) is True
        assert _is_blocked_by_boundary("capability_signals", boundaries) is False

    def test_plain_english_summary(self):
        summary = _build_plain_english_summary(
            app_name="Test App",
            purpose="improve recommendations",
            allowed=["identity_role", "capability_signals"],
            excluded=["behavior_patterns"],
            confidence_levels={"identity_role": 0.75},
        )
        assert "Test App" in summary
        assert "improve recommendations" in summary
        # Raw layer keys are replaced by human-readable labels
        assert "Your identity and professional role" in summary
        assert "Features and tools you use" in summary
        assert "How you typically work" in summary
        assert "approve" in summary.lower() or "deny" in summary.lower()
