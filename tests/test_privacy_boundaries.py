import pytest
from database import create_tables
from pcl.privacy_boundaries import (
    get_onboarding_questions,
    save_onboarding_flow_answers,
    get_user_privacy_profile,
    add_privacy_boundary,
    remove_privacy_boundary,
    deactivate_privacy_boundary,
    check_sharing_allowed,
)


@pytest.fixture(autouse=True)
def _reset_db(tmp_path, monkeypatch):
    import database
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    database.create_tables()
    yield


class TestOnboardingFlow:
    def test_get_questions(self):
        questions = get_onboarding_questions()
        assert len(questions) >= 5
        assert all("id" in q and "question" in q for q in questions)

    def test_save_onboarding_answers(self):
        answers = {
            "personalization_goals": ["app_recommendations", "coding_assistance"],
            "enabled_integrations": ["browser", "sdk"],
            "never_share": ["identity_role"],
            "privacy_level": "strict",
            "personalization_aggression": "low",
            "sharing_default": "ask",
        }
        profile = save_onboarding_flow_answers("test_user", answers)
        assert profile["onboarding_completed"] is True
        assert profile["boundary_count"] == 1

    def test_privacy_profile(self):
        profile = get_user_privacy_profile("test_user")
        assert profile["user_id"] == "test_user"
        assert "preferences" in profile
        assert "active_boundaries" in profile


class TestPrivacyBoundaries:
    def test_add_boundary(self):
        boundary = add_privacy_boundary("test_user", "never_share_app", "evil-app", "suspicious")
        assert boundary["boundary_type"] == "never_share_app"
        assert boundary["target"] == "evil-app"
        assert boundary["is_active"] is True

    def test_remove_boundary(self):
        boundary = add_privacy_boundary("test_user", "never_share_field", "identity_role")
        result = remove_privacy_boundary("test_user", boundary["id"])
        assert result["deleted"] is True

    def test_deactivate_boundary(self):
        boundary = add_privacy_boundary("test_user", "never_share_field", "identity_role")
        result = deactivate_privacy_boundary("test_user", boundary["id"])
        assert result["revoked"] is True

    def test_list_boundaries(self):
        add_privacy_boundary("test_user", "never_share_field", "identity_role")
        add_privacy_boundary("test_user", "never_share_app", "bad-app")
        profile = get_user_privacy_profile("test_user")
        assert profile["boundary_count"] == 2


class TestCheckSharing:
    def test_check_sharing_allowed(self):
        add_privacy_boundary("test_user", "never_share_field", "identity_role")
        result = check_sharing_allowed("test_user", "some-app", ["identity_role", "capability_signals"])
        assert "identity_role" in result["blocked"]
        assert "capability_signals" in result["allowed"]
        assert result["privacy_level"] == "balanced"

    def test_check_sharing_app_blocked(self):
        add_privacy_boundary("test_user", "never_share_app", "blocked-app")
        result = check_sharing_allowed("test_user", "blocked-app", ["capability_signals"])
        assert "capability_signals" in result["blocked"]

    def test_check_sharing_no_boundaries(self):
        result = check_sharing_allowed("test_user", "any-app", ["identity_role", "capability_signals"])
        assert result["blocked"] == []
        assert "identity_role" in result["allowed"]
