import time

from database import get_latest_persona, get_pcl_feature_usage, get_pcl_onboarding_seed
from living_persona import build_living_persona
from pcl.models import (
    ActiveContext,
    BehaviorPatterns,
    CapabilitySignal,
    ExplicitPreference,
    IdentityRole,
    UserContextProfile,
)


def build_local_user_context_profile(user_id: str) -> UserContextProfile:
    persona = get_latest_persona() or {}
    living = build_living_persona()
    onboarding = get_pcl_onboarding_seed(user_id) or {}
    seed = onboarding.get("profile_seed", {})

    identity = persona.get("identity", {})
    context = persona.get("context", {})
    voice = persona.get("voice", {})
    seeded_identity = seed.get("identity", {})
    seeded_behavior = seed.get("behavior", {})
    seeded_active_context = seed.get("active_context", {})

    capabilities = [
        CapabilitySignal(
            feature_id=item["name"],
            feature_name=item["name"].replace("_", " ").title(),
            use_count=max(1, int(item.get("score", 0))),
            recency_weight=min(float(item.get("score", 0)) / 10, 1.0),
            confidence=float(item.get("confidence", 0.5)),
        )
        for item in living.get("tools", [])[:20]
    ]
    capabilities.extend([
        CapabilitySignal(
            feature_id=item["feature_id"],
            feature_name=item["feature_name"],
            use_count=int(item["use_count"]),
            last_used_at=int(item["last_used_at"]) if item["last_used_at"] else None,
            recency_weight=_recency_weight(int(item["last_used_at"])) if item["last_used_at"] else 0.0,
            confidence=min(0.4 + int(item["use_count"]) * 0.08, 0.95),
        )
        for item in get_pcl_feature_usage(user_id)
    ])
    capabilities.extend([
        CapabilitySignal(**item)
        for item in seed.get("capabilities", [])
    ])

    preferences = [
        ExplicitPreference(key=item, value=False, hard_rule=True, source="persona")
        for item in persona.get("values", {}).get("dislikes", [])
        if isinstance(item, str)
    ]
    preferences.extend([
        ExplicitPreference(**item)
        for item in seed.get("explicit_preferences", [])
    ])

    return UserContextProfile(
        user_id=user_id,
        identity=IdentityRole(
            role=identity.get("role", "") or seeded_identity.get("role", ""),
            domain=(living.get("work_domains", [{}]) or [{}])[0].get("name", "") or seeded_identity.get("domain", ""),
            skill_level=seeded_identity.get("skill_level", "") or "unknown",
            current_project=identity.get("current_project", "") or seeded_identity.get("current_project", ""),
            expertise=identity.get("expertise", []) or seeded_identity.get("expertise", []),
        ),
        capabilities=capabilities,
        behavior=BehaviorPatterns(
            active_hours=context.get("active_hours", ""),
            workflow_style=voice.get("style", "") or seeded_behavior.get("workflow_style", ""),
            preferred_depth=seeded_behavior.get("preferred_depth", "unknown"),
        ),
        active_context=ActiveContext(
            current_project=context.get("building", identity.get("current_project", "")) or seeded_active_context.get("current_project", ""),
            active_tools=[item["name"] for item in living.get("tools", [])[:8]],
            current_goal=context.get("building", "") or seeded_active_context.get("current_goal", ""),
            blockers=[context["blocked_on"]] if context.get("blocked_on") else [],
        ),
        explicit_preferences=preferences,
        meta={
            "source": "local_daemon_projection",
            "living_model": living.get("meta", {}).get("model"),
        },
    )


def _recency_weight(timestamp: int) -> float:
    age_ms = max(0, int(time.time() * 1000) - timestamp)
    age_days = age_ms / (1000 * 60 * 60 * 24)
    return round(max(0.0, min(1.0, 1 - (age_days / 30))), 3)
