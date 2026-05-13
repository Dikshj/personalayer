import time
from typing import Any

from database import insert_raw_context_event, list_feature_signals, update_user_profile_record


COLD_START_PROMPT = """Given a user who is [role] in [domain] at [skill_level] skill,
and an app called [app_name] with these features [feature_list], generate a plausible
initial feature usage distribution as JSON. Assign higher recency_score to features
typically used by someone in this role. Output only JSON."""


ROLE_PRIORS = {
    "designer": ["auto-layout", "components", "prototyping", "design-system", "comments"],
    "engineer": ["pull-requests", "issues", "actions", "search", "code-review"],
    "product": ["roadmap", "views", "database-view", "comments", "calendar"],
    "founder": ["dashboard", "inbox", "calendar", "roadmap", "analytics"],
    "student": ["search", "notes", "calendar", "flashcards", "summaries"],
}


def generate_cold_start_signals(
    user_id: str,
    app_id: str,
    app_name: str = "",
    features: list[str] | None = None,
    role: str = "",
    domain: str = "",
    skill_level: str = "intermediate",
) -> dict[str, Any]:
    existing = list_feature_signals(user_id=user_id, app_id=app_id, active_only=False)
    if existing:
        return {"status": "skipped", "reason": "existing_signals", "signals_created": 0}

    normalized_features = [_slug(feature) for feature in (features or []) if _slug(feature)]
    if not normalized_features:
        normalized_features = _features_from_role(role)
    normalized_features = normalized_features[:8]

    now_ms = int(time.time() * 1000)
    created = []
    for index, feature_id in enumerate(normalized_features):
        event = insert_raw_context_event({
            "user_id": user_id,
            "app_id": app_id,
            "feature_id": feature_id,
            "action": "used",
            "session_id": f"synthetic-{app_id}",
            "source": "onboarding",
            "is_synthetic": True,
            "metadata": {
                "hour_of_day": 9 + min(index, 8),
                "day_of_week": 1,
                "subject_category": _slug(domain or role or app_name or "general"),
            },
            "timestamp": now_ms - (index * 60_000),
        })
        created.append(event["feature_id"])

    update_user_profile_record(
        user_id,
        timezone="UTC",
        abstract_attributes=[{
            "attribute": "cold-start-profile",
            "value": f"{role or 'unknown'} in {domain or 'unknown'} using {app_name or app_id}",
            "confidence": 0.3,
            "evidence_count": len(created),
            "layer": "identity",
        }],
    )
    return {
        "status": "ok",
        "signals_created": len(created),
        "features": created,
        "is_synthetic": True,
        "confidence": 0.3,
        "prompt_template": COLD_START_PROMPT,
    }


def _features_from_role(role: str) -> list[str]:
    lowered = role.lower()
    for key, features in ROLE_PRIORS.items():
        if key in lowered:
            return features
    return ["search", "dashboard", "notifications", "settings", "comments"]


def _slug(value: str) -> str:
    chars = [char if char.isalnum() else "-" for char in str(value).lower()]
    return "-".join("".join(chars).split("-")).strip("-")
