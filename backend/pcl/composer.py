import time
from typing import Any

from pcl.models import (
    AppFeature,
    ContextLayer,
    ContextQuery,
    DecisionBundle,
    RankedFeature,
    UserContextProfile,
)
from pcl.privacy import scrub_pii


DEFAULT_ALLOWED_LAYERS: list[ContextLayer] = [
    "identity_role",
    "capability_signals",
    "behavior_patterns",
    "active_context",
    "explicit_preferences",
]


def compose_decision_bundle(
    query: ContextQuery,
    profile: UserContextProfile,
    allowed_layers: list[ContextLayer] | None = None,
) -> DecisionBundle:
    allowed = allowed_layers or query.requested_layers or DEFAULT_ALLOWED_LAYERS
    ranked = rank_features(query.features, profile)

    return DecisionBundle(
        app_id=query.app_id,
        user_id=query.user_id,
        purpose=query.purpose,
        allowed_layers=allowed,
        ranked_features=ranked,
        constraints=_constraints(profile),
        context=_context_for_layers(profile, allowed),
        audit={
            "raw_data_shared": False,
            "apps_may_store_copy": False,
            "query_logged": True,
            "generated_at": int(time.time() * 1000),
        },
    )


def rank_features(features: list[AppFeature], profile: UserContextProfile) -> list[RankedFeature]:
    usage = {item.feature_id: item for item in profile.capabilities}
    ranked: list[RankedFeature] = []

    for feature in features:
        signal = usage.get(feature.feature_id)
        score = 0.0
        reasons = []
        confidence = 0.25

        if signal:
            score += min(signal.use_count, 25) * 0.8
            score += signal.recency_weight * 10
            confidence = max(confidence, signal.confidence)
            reasons.append("feature_usage")
            if signal.last_used_at:
                reasons.append("recent_use")

        if feature.category and feature.category in profile.identity.expertise:
            score += 3
            reasons.append("identity_fit")

        if feature.name.lower() in {pref.key.lower() for pref in profile.explicit_preferences if pref.value is False}:
            score -= 100
            reasons.append("explicitly_disabled")

        ranked.append(RankedFeature(
            feature_id=feature.feature_id,
            name=feature.name,
            rank=0,
            score=round(score, 3),
            reason_codes=reasons or ["no_signal"],
            confidence=round(confidence, 3),
        ))

    ranked.sort(key=lambda item: item.score, reverse=True)
    return [
        item.model_copy(update={"rank": index + 1})
        for index, item in enumerate(ranked)
    ]


def _constraints(profile: UserContextProfile) -> dict[str, Any]:
    constraints = {
        pref.key: pref.value
        for pref in profile.explicit_preferences
        if pref.hard_rule
    }
    return scrub_pii(constraints)


def _context_for_layers(profile: UserContextProfile, layers: list[ContextLayer]) -> dict[str, Any]:
    context: dict[str, Any] = {}
    if "identity_role" in layers:
        context["identity_role"] = profile.identity.model_dump()
    if "capability_signals" in layers:
        context["capability_signals"] = [item.model_dump() for item in profile.capabilities[:20]]
    if "behavior_patterns" in layers:
        context["behavior_patterns"] = profile.behavior.model_dump()
    if "active_context" in layers:
        context["active_context"] = profile.active_context.model_dump()
    if "explicit_preferences" in layers:
        context["explicit_preferences"] = [
            item.model_dump() for item in profile.explicit_preferences
        ]
    return scrub_pii(context)
