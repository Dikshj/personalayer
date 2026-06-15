from typing import Any, Optional

from database import (
    delete_persona_signal,
    export_user_context_data,
    get_persona_signal_by_id,
    get_unified_permissions,
    insert_control_center_audit,
    list_control_center_audit,
    list_privacy_boundaries,
    revoke_privacy_boundary,
    search_persona_signals,
    update_persona_signal,
)
from pcl.privacy import scrub_pii


SIGNAL_TYPE_LABELS = {
    "interest": "Interest",
    "skill": "Skill",
    "tool": "Tool",
    "work_domain": "Work Domain",
    "task_pattern": "Task Pattern",
    "behavior": "Behavior",
    "preference": "Preference",
}

SOURCE_LABELS = {
    "browser": "Browser Activity",
    "extension": "Browser Extension",
    "sdk": "SDK Integration",
    "connector": "Third-party Connector",
    "onboarding": "Onboarding Seed",
    "manual": "Manually Added",
    "inferred": "AI Inferred",
}


def get_control_center_summary(user_id: str) -> dict:
    audit = list_control_center_audit(user_id, limit=1)
    boundaries = list_privacy_boundaries(user_id, active_only=True)
    permissions = get_unified_permissions(user_id)
    return {
        "user_id": user_id,
        "active_permissions": len([p for p in permissions if p["status"] == "active"]),
        "revoked_permissions": len([p for p in permissions if p["status"] == "revoked"]),
        "privacy_boundaries": len(boundaries),
        "last_control_center_action": audit[0] if audit else None,
    }


def search_signals(
    user_id: str,
    query: str = "",
    source: Optional[str] = None,
    signal_type: Optional[str] = None,
    shareable_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    signals = search_persona_signals(
        query=query,
        source=source,
        signal_type=signal_type,
        shareable_only=shareable_only,
        limit=limit,
        offset=offset,
    )
    for signal in signals:
        signal["human_readable_source"] = SOURCE_LABELS.get(signal["source"], signal["source"])
        signal["human_readable_type"] = SIGNAL_TYPE_LABELS.get(signal["signal_type"], signal["signal_type"])
        signal["why_it_exists"] = _explain_signal_origin(signal)
        signal["currently_shareable"] = signal["shareable"]
    insert_control_center_audit(
        user_id=user_id,
        action="search_signals",
        target_type="signals",
        details={"query": query, "source": source, "signal_type": signal_type, "results": len(signals)},
    )
    return {
        "signals": signals,
        "count": len(signals),
        "query": query,
    }


def _explain_signal_origin(signal: dict) -> str:
    source = signal.get("source", "unknown")
    stype = signal.get("signal_type", "unknown")
    evidence = signal.get("evidence", "")
    if source == "browser":
        return f"Detected from your browsing activity. {evidence}".strip()
    if source == "extension":
        return f"Collected by the browser extension. {evidence}".strip()
    if source == "sdk":
        return f"Reported by an integrated app via SDK. {evidence}".strip()
    if source == "onboarding":
        return f"You provided this during onboarding. {evidence}".strip()
    if source == "inferred":
        return f"Inferred by PersonaLayer from your activity patterns. {evidence}".strip()
    return f"Source: {source}. {evidence}".strip()


def edit_signal(
    user_id: str,
    signal_id: int,
    name: Optional[str] = None,
    weight: Optional[float] = None,
    confidence: Optional[float] = None,
    evidence: Optional[str] = None,
    shareable: Optional[bool] = None,
    reason: str = "",
) -> dict:
    updated = update_persona_signal(
        signal_id=signal_id,
        user_id=user_id,
        name=name,
        weight=weight,
        confidence=confidence,
        evidence=evidence,
        shareable=shareable,
        edit_reason=reason,
    )
    insert_control_center_audit(
        user_id=user_id,
        action="edit_signal",
        target_type="signal",
        target_id=str(signal_id),
        details={"reason": reason},
    )
    return updated


def remove_signal(user_id: str, signal_id: int) -> dict:
    deleted = delete_persona_signal(signal_id=signal_id, user_id=user_id)
    insert_control_center_audit(
        user_id=user_id,
        action="delete_signal",
        target_type="signal",
        target_id=str(signal_id),
    )
    return {"deleted": deleted, "signal_id": signal_id}


def get_signal_detail(user_id: str, signal_id: int) -> dict:
    signal = get_persona_signal_by_id(signal_id)
    if not signal:
        return {"error": "signal_not_found"}
    signal["human_readable_source"] = SOURCE_LABELS.get(signal["source"], signal["source"])
    signal["human_readable_type"] = SIGNAL_TYPE_LABELS.get(signal["signal_type"], signal["signal_type"])
    signal["why_it_exists"] = _explain_signal_origin(signal)
    return signal


def export_user_data(user_id: str, format: str = "json") -> dict:
    raw = export_user_context_data(user_id)
    safe = scrub_pii(raw)
    insert_control_center_audit(
        user_id=user_id,
        action="export_data",
        target_type="user_data",
        details={"format": format, "signals_count": len(safe.get("signals", []))},
    )
    return {
        "user_id": user_id,
        "format": format,
        "exported_at": safe["exported_at"],
        "data": safe,
    }


def get_unified_permission_list(user_id: str) -> dict:
    permissions = get_unified_permissions(user_id)
    active = [p for p in permissions if p["status"] == "active"]
    revoked = [p for p in permissions if p["status"] == "revoked"]
    expired = [p for p in permissions if p["status"] == "expired"]
    return {
        "user_id": user_id,
        "all_permissions": permissions,
        "active": active,
        "revoked": revoked,
        "expired": expired,
        "counts": {
            "total": len(permissions),
            "active": len(active),
            "revoked": len(revoked),
            "expired": len(expired),
        },
    }


def revoke_permission_by_id(user_id: str, permission_id: str, permission_type: str) -> dict:
    if permission_type == "app":
        from database import revoke_app_consent
        revoked = revoke_app_consent(user_id=user_id, app_id=permission_id)
    elif permission_type == "domain":
        from database import revoke_web_domain_permission
        revoked = revoke_web_domain_permission(user_id=user_id, domain=permission_id)
    elif permission_type == "contract":
        from database import revoke_context_contract
        revoked = revoke_context_contract(permission_id)
    elif permission_type == "boundary":
        revoked = revoke_privacy_boundary(permission_id)
    else:
        return {"error": "unknown_permission_type"}
    insert_control_center_audit(
        user_id=user_id,
        action="revoke_permission",
        target_type=permission_type,
        target_id=permission_id,
        details={"revoked": revoked},
    )
    return {"revoked": revoked, "permission_id": permission_id, "type": permission_type}


def get_control_center_audit_log(user_id: str, limit: int = 100) -> dict:
    logs = list_control_center_audit(user_id, limit=limit)
    return {
        "user_id": user_id,
        "logs": logs,
        "count": len(logs),
    }
