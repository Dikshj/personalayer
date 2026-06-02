from typing import Any

from database import (
    decide_context_sharing_preview,
    get_context_sharing_preview,
    insert_context_sharing_preview,
    insert_control_center_audit,
    list_context_sharing_previews,
    list_privacy_boundaries,
)
from pcl.models import ContextLayer
from pcl.profile import build_local_user_context_profile


LAYER_LABELS = {
    "identity_role": "Your identity and professional role",
    "capability_signals": "Features and tools you use",
    "behavior_patterns": "How you typically work",
    "active_context": "What you are currently focused on",
    "explicit_preferences": "Your stated preferences",
}

CONFIDENCE_LABELS = {
    (0.0, 0.3): "Low confidence — inferred from limited data",
    (0.3, 0.6): "Medium confidence — based on some patterns",
    (0.6, 0.8): "High confidence — well-supported by data",
    (0.8, 1.0): "Very high confidence — strongly verified",
}


def _confidence_label(score: float) -> str:
    for (low, high), label in CONFIDENCE_LABELS.items():
        if low <= score < high:
            return label
    return CONFIDENCE_LABELS[(0.8, 1.0)]


def generate_context_preview(
    user_id: str,
    app_id: str,
    app_name: str,
    requested_purpose: str,
    requested_layers: list[ContextLayer],
    requested_scopes: list[str],
) -> dict:
    profile = build_local_user_context_profile(user_id)
    boundaries = list_privacy_boundaries(user_id, active_only=True)

    allowed_fields = []
    excluded_fields = []
    confidence_levels = {}

    for layer in requested_layers:
        layer_str = str(layer)
        if _is_blocked_by_boundary(layer_str, boundaries):
            excluded_fields.append(layer_str)
            continue
        allowed_fields.append(layer_str)
        confidence_levels[layer_str] = _estimate_confidence(layer_str, profile)

    plain_english = _build_plain_english_summary(
        app_name=app_name,
        purpose=requested_purpose,
        allowed=allowed_fields,
        excluded=excluded_fields,
        confidence_levels=confidence_levels,
    )

    preview_json = {
        "app_id": app_id,
        "app_name": app_name,
        "purpose": requested_purpose,
        "requested_layers": [str(l) for l in requested_layers],
        "allowed_layers": allowed_fields,
        "excluded_layers": excluded_fields,
        "confidence_levels": confidence_levels,
        "profile_preview": _build_profile_preview(profile, allowed_fields),
    }

    preview = insert_context_sharing_preview(
        user_id=user_id,
        app_id=app_id,
        app_name=app_name,
        requested_purpose=requested_purpose,
        permission_scope=requested_scopes,
        allowed_fields=allowed_fields,
        excluded_fields=excluded_fields,
        confidence_levels=confidence_levels,
        plain_english_summary=plain_english,
        preview_json=preview_json,
    )
    insert_control_center_audit(
        user_id=user_id,
        action="generate_preview",
        target_type="context_preview",
        target_id=preview["id"],
        details={"app_id": app_id, "purpose": requested_purpose},
    )
    return preview


def _is_blocked_by_boundary(layer: str, boundaries: list[dict]) -> bool:
    for boundary in boundaries:
        if boundary["boundary_type"] == "never_share_field" and boundary["target"] == layer:
            return True
    return False


def _estimate_confidence(layer: str, profile: Any) -> float:
    if layer == "identity_role":
        return 0.75 if profile.identity.role else 0.2
    if layer == "capability_signals":
        return 0.7 if profile.capabilities else 0.15
    if layer == "behavior_patterns":
        return 0.6 if profile.behavior.workflow_style else 0.1
    if layer == "active_context":
        return 0.65 if profile.active_context.current_project else 0.1
    if layer == "explicit_preferences":
        return 0.8 if profile.explicit_preferences else 0.1
    return 0.5


def _build_plain_english_summary(
    app_name: str,
    purpose: str,
    allowed: list[str],
    excluded: list[str],
    confidence_levels: dict,
) -> str:
    parts = [f'"{app_name}" wants to access your personal context to {purpose or "personalize your experience"}.']
    if allowed:
        parts.append(f"It will receive: {', '.join(LAYER_LABELS.get(a, a) for a in allowed)}.")
    if excluded:
        parts.append(f"It will NOT receive: {', '.join(LAYER_LABELS.get(e, e) for e in excluded)}.")
    if confidence_levels:
        confidences = [_confidence_label(v) for v in confidence_levels.values()]
        parts.append(f"Data confidence: {', '.join(confidences)}.")
    parts.append("You can approve, deny, or choose which fields to share.")
    return " ".join(parts)


def _build_profile_preview(profile: Any, allowed_layers: list[str]) -> dict:
    preview = {}
    if "identity_role" in allowed_layers:
        preview["identity_role"] = {
            "role": profile.identity.role or "Not yet identified",
            "domain": profile.identity.domain or "",
            "skill_level": profile.identity.skill_level or "",
        }
    if "capability_signals" in allowed_layers:
        preview["capability_signals"] = [
            {"feature": c.feature_name, "uses": c.use_count}
            for c in profile.capabilities[:5]
        ] or ["No capabilities recorded yet"]
    if "behavior_patterns" in allowed_layers:
        preview["behavior_patterns"] = {
            "workflow_style": profile.behavior.workflow_style or "Not yet identified",
            "preferred_depth": profile.behavior.preferred_depth,
        }
    if "active_context" in allowed_layers:
        preview["active_context"] = {
            "current_project": profile.active_context.current_project or "Not identified",
            "active_tools": profile.active_context.active_tools[:3] if profile.active_context.active_tools else [],
        }
    if "explicit_preferences" in allowed_layers:
        preview["explicit_preferences"] = [
            {"key": p.key, "value": str(p.value)[:100]}
            for p in profile.explicit_preferences[:5]
        ] or ["No explicit preferences recorded yet"]
    return preview


def handle_preview_decision(
    preview_id: str,
    decision: str,
    narrowed_fields: list[str] | None = None,
    user_decision: str = "",
) -> dict:
    preview = get_context_sharing_preview(preview_id)
    if not preview:
        return {"error": "preview_not_found"}
    if preview["status"] != "pending":
        return {"error": "preview_already_decided", "status": preview["status"]}
    result = decide_context_sharing_preview(
        preview_id=preview_id,
        decision=decision,
        narrowed_fields=narrowed_fields,
        user_decision=user_decision,
    )
    insert_control_center_audit(
        user_id=preview["user_id"],
        action=f"preview_{decision}",
        target_type="context_preview",
        target_id=preview_id,
        details={
            "app_id": preview["app_id"],
            "decision": decision,
            "narrowed_fields": narrowed_fields,
        },
    )
    return result


def get_preview_history(user_id: str, limit: int = 50) -> dict:
    previews = list_context_sharing_previews(user_id=user_id, limit=limit)
    return {
        "user_id": user_id,
        "previews": previews,
        "count": len(previews),
    }
