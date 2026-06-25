from typing import Any, Optional

from database import (
    delete_privacy_boundary,
    get_user_preferences,
    insert_control_center_audit,
    insert_privacy_boundary,
    list_privacy_boundaries,
    revoke_privacy_boundary,
    upsert_user_preferences,
)


class PrivacyBoundaryError(Exception):
    """Raised when a privacy boundary check fails."""
    pass


def check_domain_approved(domain: str) -> None:
    """Check if a domain is approved for extension bridge access.

    Allows localhost and extension origins unconditionally.
    For web domains, checks the persisted web_domain_permissions table.
    """
    if not domain:
        raise PrivacyBoundaryError("Domain is required for extension bridge access")
    allowed_prefixes = ("localhost", "127.0.0.1", "chrome-extension://", "safari-web-extension://")
    if any(domain.startswith(prefix) for prefix in allowed_prefixes):
        return
    # Check persisted domain approval
    from database import get_web_domain_permission
    permission = get_web_domain_permission("default", domain)
    if permission and permission.get("is_active"):
        return
    raise PrivacyBoundaryError(f"Domain {domain} is not approved for extension bridge access")


def check_extension_origin(origin: str) -> None:
    """Check if an extension origin is allowed."""
    if not origin:
        raise PrivacyBoundaryError("Origin is required")
    allowed_prefixes = ("chrome-extension://", "safari-web-extension://", "moz-extension://")
    if any(origin.startswith(prefix) for prefix in allowed_prefixes):
        return
    raise PrivacyBoundaryError(f"Origin {origin} is not an allowed extension origin")


ONBOARDING_FLOW_QUESTIONS = [
    {
        "id": "personalization_goals",
        "category": "goals",
        "question": "What do you want PersonaLayer to personalize for you?",
        "description": "Choose the areas where personalized context would help you most.",
        "options": [
            {"value": "app_recommendations", "label": "App and tool recommendations"},
            {"value": "workflow_optimization", "label": "Workflow optimization"},
            {"value": "content_curation", "label": "Content and feed curation"},
            {"value": "coding_assistance", "label": "Coding and development assistance"},
            {"value": "meeting_prep", "label": "Meeting preparation"},
            {"value": "learning_paths", "label": "Personalized learning paths"},
        ],
        "multiple": True,
    },
    {
        "id": "enabled_integrations",
        "category": "sources",
        "question": "Which data sources should PersonaLayer use to understand you?",
        "description": "You can enable or disable any source at any time.",
        "options": [
            {"value": "browser", "label": "Browser activity"},
            {"value": "extension", "label": "Browser extension signals"},
            {"value": "sdk", "label": "App SDK integrations"},
            {"value": "github", "label": "GitHub activity"},
            {"value": "manual", "label": "Manual entries"},
        ],
        "multiple": True,
    },
    {
        "id": "never_share",
        "category": "boundaries",
        "question": "What should PersonaLayer NEVER share with apps?",
        "description": "These fields will be completely blocked from sharing.",
        "options": [
            {"value": "identity_role", "label": "Your identity or job role"},
            {"value": "behavior_patterns", "label": "Your behavior patterns"},
            {"value": "active_context", "label": "Your current activity or project"},
            {"value": "explicit_preferences", "label": "Your explicit preferences"},
        ],
        "multiple": True,
    },
    {
        "id": "privacy_level",
        "category": "privacy",
        "question": "How protective do you want your default privacy settings to be?",
        "description": "This controls the default for new apps and integrations.",
        "options": [
            {"value": "strict", "label": "Strict — ask me before sharing anything"},
            {"value": "balanced", "label": "Balanced — ask for sensitive fields only"},
            {"value": "permissive", "label": "Permissive — share low-sensitivity data automatically"},
        ],
        "multiple": False,
    },
    {
        "id": "personalization_aggression",
        "category": "personalization",
        "question": "How aggressively should PersonaLayer personalize?",
        "description": "Higher aggression means more proactive personalization, but more data usage.",
        "options": [
            {"value": "low", "label": "Low — minimal personalization, maximum privacy"},
            {"value": "medium", "label": "Medium — balanced personalization and privacy"},
            {"value": "high", "label": "High — aggressive personalization, more data collection"},
        ],
        "multiple": False,
    },
    {
        "id": "sharing_default",
        "category": "sharing",
        "question": "When a new app requests your context, what should the default be?",
        "description": "You can always override this for individual apps.",
        "options": [
            {"value": "ask", "label": "Always ask me first"},
            {"value": "allow", "label": "Allow low-sensitivity context by default"},
            {"value": "deny", "label": "Deny by default unless I explicitly allow"},
        ],
        "multiple": False,
    },
]


def get_onboarding_questions() -> list[dict]:
    return ONBOARDING_FLOW_QUESTIONS


def save_onboarding_flow_answers(user_id: str, answers: dict[str, Any]) -> dict:
    # Missing fields mean "leave the current value unchanged". Completing
    # onboarding via Skip must not erase preferences or integrations.
    goals = answers.get("personalization_goals")
    integrations = answers.get("enabled_integrations")
    never_share = answers.get("never_share", [])
    privacy_level = answers.get("privacy_level")
    personalization_aggression = answers.get("personalization_aggression")
    sharing_default = answers.get("sharing_default")

    upsert_user_preferences(
        user_id=user_id,
        personalization_goals=goals,
        privacy_level=privacy_level,
        sharing_default=sharing_default,
        personalization_aggression=personalization_aggression,
        enabled_integrations=integrations,
        onboarding_completed=True,
    )

    for field in never_share:
        insert_privacy_boundary(
            user_id=user_id,
            boundary_type="never_share_field",
            target=field,
            reason="User selected during onboarding as never-share",
        )

    insert_control_center_audit(
        user_id=user_id,
        action="complete_onboarding",
        target_type="user_preferences",
        details={
            "goals": goals if goals is not None else [],
            "integrations": integrations if integrations is not None else [],
            "never_share": never_share,
            "privacy_level": privacy_level or "unchanged",
        },
    )
    return get_user_privacy_profile(user_id)


def get_user_privacy_profile(user_id: str) -> dict:
    preferences = get_user_preferences(user_id)
    boundaries = list_privacy_boundaries(user_id, active_only=True)
    return {
        "user_id": user_id,
        "preferences": preferences,
        "active_boundaries": boundaries,
        "boundary_count": len(boundaries),
        "onboarding_completed": preferences.get("onboarding_completed", False),
    }


def add_privacy_boundary(
    user_id: str,
    boundary_type: str,
    target: str,
    reason: str = "",
) -> dict:
    boundary = insert_privacy_boundary(
        user_id=user_id,
        boundary_type=boundary_type,
        target=target,
        reason=reason,
    )
    insert_control_center_audit(
        user_id=user_id,
        action="add_boundary",
        target_type="privacy_boundary",
        target_id=boundary["id"],
        details={"boundary_type": boundary_type, "target": target},
    )
    return boundary


def remove_privacy_boundary(user_id: str, boundary_id: str) -> dict:
    deleted = delete_privacy_boundary(boundary_id)
    insert_control_center_audit(
        user_id=user_id,
        action="delete_boundary",
        target_type="privacy_boundary",
        target_id=boundary_id,
    )
    return {"deleted": deleted, "boundary_id": boundary_id}


def deactivate_privacy_boundary(user_id: str, boundary_id: str) -> dict:
    revoked = revoke_privacy_boundary(boundary_id)
    insert_control_center_audit(
        user_id=user_id,
        action="deactivate_boundary",
        target_type="privacy_boundary",
        target_id=boundary_id,
    )
    return {"revoked": revoked, "boundary_id": boundary_id}


def check_sharing_allowed(
    user_id: str,
    app_id: str,
    fields: list[str],
) -> dict:
    preferences = get_user_preferences(user_id)
    boundaries = list_privacy_boundaries(user_id, active_only=True)
    blocked = []
    allowed = []
    for field in fields:
        is_blocked = False
        for boundary in boundaries:
            if boundary["boundary_type"] == "never_share_field" and boundary["target"] == field:
                is_blocked = True
                break
            if boundary["boundary_type"] == "never_share_app" and boundary["target"] == app_id:
                is_blocked = True
                break
        if is_blocked:
            blocked.append(field)
        else:
            allowed.append(field)
    return {
        "user_id": user_id,
        "app_id": app_id,
        "allowed": allowed,
        "blocked": blocked,
        "sharing_default": preferences.get("sharing_default", "ask"),
        "privacy_level": preferences.get("privacy_level", "balanced"),
    }
