from typing import Any

from pcl.privacy import scrub_pii


ONBOARDING_QUESTIONS = [
    {
        "id": "identity",
        "layer": "identity_role",
        "question": "What do you do, and what domain should apps understand you operate in?",
    },
    {
        "id": "features",
        "layer": "capability_signals",
        "question": "Which app features or workflows do you use most often?",
    },
    {
        "id": "behavior",
        "layer": "behavior_patterns",
        "question": "How do you usually work: quick minimal flows, deep detailed flows, or something else?",
    },
    {
        "id": "active_context",
        "layer": "active_context",
        "question": "What are you focused on right now?",
    },
    {
        "id": "preferences",
        "layer": "explicit_preferences",
        "question": "What should apps always do or never do for you?",
    },
]


def build_onboarding_seed(answers: dict[str, Any]) -> dict:
    clean = scrub_pii(answers)
    identity = str(clean.get("identity", "")).strip()
    features = _split_items(clean.get("features", ""))
    behavior = str(clean.get("behavior", "")).strip()
    active = str(clean.get("active_context", "")).strip()
    preferences = _split_items(clean.get("preferences", ""))

    return {
        "identity": _identity_seed(identity),
        "capabilities": [
            {
                "feature_id": _slug(item),
                "feature_name": item,
                "use_count": 1,
                "recency_weight": 0.5,
                "confidence": 0.45,
            }
            for item in features
        ],
        "behavior": {
            "workflow_style": behavior,
            "preferred_depth": _preferred_depth(behavior),
        },
        "active_context": {
            "current_project": active,
            "current_goal": active,
        },
        "explicit_preferences": [
            {
                "key": item,
                "value": False if _looks_negative(item) else True,
                "hard_rule": True,
                "source": "onboarding",
            }
            for item in preferences
        ],
    }


def _identity_seed(value: str) -> dict:
    parts = [part.strip() for part in value.split(",") if part.strip()]
    return {
        "role": parts[0] if parts else value,
        "domain": parts[1] if len(parts) > 1 else "",
        "skill_level": "",
        "current_project": "",
        "expertise": parts[2:] if len(parts) > 2 else [],
    }


def _split_items(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value)
    for separator in ["\n", ";"]:
        text = text.replace(separator, ",")
    return [item.strip(" .") for item in text.split(",") if item.strip(" .")]


def _preferred_depth(value: str) -> str:
    lowered = value.lower()
    if any(word in lowered for word in ["quick", "minimal", "brief", "simple"]):
        return "minimal"
    if any(word in lowered for word in ["deep", "detailed", "thorough"]):
        return "detailed"
    if lowered:
        return "balanced"
    return "unknown"


def _looks_negative(value: str) -> bool:
    lowered = value.lower()
    return any(word in lowered for word in ["never", "don't", "dont", "avoid", "disable", "turn off"])


def _slug(value: str) -> str:
    lowered = value.lower()
    chars = [char if char.isalnum() else "_" for char in lowered]
    return "_".join("".join(chars).split("_")).strip("_")
