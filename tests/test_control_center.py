import pytest
from database import (
    create_tables,
    get_connection,
    insert_persona_signal,
    register_pcl_app,
    grant_app_consent,
    save_context_contract,
    insert_context_access_log,
    get_user_preferences,
    upsert_user_preferences,
    insert_privacy_boundary,
)
from pcl.control_center import (
    get_control_center_summary,
    search_signals,
    edit_signal,
    remove_signal,
    get_signal_detail,
    export_user_data,
    get_unified_permission_list,
    revoke_permission_by_id,
    get_control_center_audit_log,
)


@pytest.fixture(autouse=True)
def _reset_db(tmp_path, monkeypatch):
    import database
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    database.create_tables()
    yield


class TestControlCenterSummary:
    def test_empty_summary(self):
        summary = get_control_center_summary("test_user")
        assert summary["user_id"] == "test_user"
        assert summary["active_permissions"] == 0
        assert summary["revoked_permissions"] == 0
        assert summary["privacy_boundaries"] == 0
        assert summary["last_control_center_action"] is None

    def test_summary_with_data(self):
        upsert_user_preferences("test_user", privacy_level="strict")
        insert_privacy_boundary("test_user", "never_share_field", "identity_role")
        register_pcl_app("app1", "Test App", ["identity_role"])
        grant_app_consent("test_user", "app1", ["getFeatureUsage"])
        summary = get_control_center_summary("test_user")
        assert summary["active_permissions"] == 1
        assert summary["privacy_boundaries"] == 1


class TestSignalSearch:
    def test_search_empty(self):
        result = search_signals("test_user", query="python")
        assert result["count"] == 0
        assert result["signals"] == []

    def test_search_with_signals(self):
        ts = 1700000000000
        insert_persona_signal("browser", "interest", "python", 1.0, 0.8, "visited docs", ts)
        insert_persona_signal("sdk", "skill", "javascript", 0.8, 0.6, "project usage", ts)
        result = search_signals("test_user", query="python")
        assert result["count"] == 1
        assert result["signals"][0]["name"] == "python"
        assert result["signals"][0]["human_readable_source"] == "Browser Activity"

    def test_search_by_source(self):
        ts = 1700000000000
        insert_persona_signal("browser", "interest", "python", 1.0, 0.8, "", ts)
        insert_persona_signal("sdk", "skill", "js", 0.8, 0.6, "", ts)
        result = search_signals("test_user", source="browser")
        assert result["count"] == 1
        assert result["signals"][0]["source"] == "browser"

    def test_shareable_only_filter(self):
        ts = 1700000000000
        insert_persona_signal("browser", "interest", "public", 1.0, 0.8, "", ts, shareable=True)
        insert_persona_signal("browser", "interest", "private", 1.0, 0.8, "", ts, shareable=False)
        result = search_signals("test_user", shareable_only=True)
        assert result["count"] == 1
        assert result["signals"][0]["name"] == "public"


class TestSignalEditAndDelete:
    def test_edit_signal(self):
        ts = 1700000000000
        insert_persona_signal("browser", "interest", "python", 1.0, 0.8, "", ts)
        updated = edit_signal("test_user", 1, name="python programming", confidence=0.95, reason="clarified")
        assert updated["name"] == "python programming"
        assert updated["confidence"] == 0.95

    def test_delete_signal(self):
        ts = 1700000000000
        insert_persona_signal("browser", "interest", "python", 1.0, 0.8, "", ts)
        result = remove_signal("test_user", 1)
        assert result["deleted"] is True
        detail = get_signal_detail("test_user", 1)
        assert "error" in detail

    def test_signal_detail(self):
        ts = 1700000000000
        insert_persona_signal("browser", "interest", "python", 1.0, 0.8, "visited docs", ts)
        detail = get_signal_detail("test_user", 1)
        assert detail["name"] == "python"
        assert "why_it_exists" in detail


class TestExport:
    def test_export_data(self):
        upsert_user_preferences("test_user", privacy_level="strict")
        result = export_user_data("test_user")
        assert result["user_id"] == "test_user"
        assert result["format"] == "json"
        assert "data" in result


class TestUnifiedPermissions:
    def test_empty_permissions(self):
        result = get_unified_permission_list("test_user")
        assert result["counts"]["total"] == 0

    def test_with_permissions(self):
        register_pcl_app("app1", "Test App", ["identity_role"])
        grant_app_consent("test_user", "app1", ["getFeatureUsage"])
        save_context_contract({
            "contract_id": "c1",
            "platform_type": "web",
            "facilities": ["read"],
            "granted_context": ["identity"],
            "denied_context": [],
        })
        result = get_unified_permission_list("test_user")
        assert result["counts"]["total"] >= 1


class TestRevokePermission:
    def test_revoke_app_permission(self):
        register_pcl_app("app1", "Test App", ["identity_role"])
        grant_app_consent("test_user", "app1", ["getFeatureUsage"])
        result = revoke_permission_by_id("test_user", "app1", "app")
        assert result["revoked"] is True

    def test_revoke_unknown_type(self):
        result = revoke_permission_by_id("test_user", "x", "unknown")
        assert "error" in result


class TestAuditLog:
    def test_audit_log(self):
        search_signals("test_user", query="test")
        logs = get_control_center_audit_log("test_user")
        assert logs["count"] >= 1
        assert logs["logs"][0]["action"] == "search_signals"
