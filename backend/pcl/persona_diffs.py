from __future__ import annotations

from typing import Optional

from database import (
    create_persona_memory_diff,
    decide_persona_memory_diff,
    get_memory_source_setting,
    get_persona_memory_diff,
    insert_control_center_audit,
    list_persona_memory_diffs,
)
from pcl.memory import append_memory_entry, read_memory_file


def propose_memory_diff(
    user_id: str,
    scope: str,
    proposed_content: str,
    reason: str = "",
    source: str = "manual",
    auto_apply: bool = True,
) -> dict:
    source_setting = get_memory_source_setting(user_id, source)
    if not source_setting["enabled"]:
        insert_control_center_audit(
            user_id=user_id,
            action="memory_ingest_skipped",
            target_type="memory_source",
            target_id=source,
            details={"scope": scope, "reason": "source_disabled"},
        )
        return {
            "status": "skipped_source_disabled",
            "user_id": user_id,
            "scope": scope,
            "source": source,
        }
    current = read_memory_file(user_id, scope)["content"]
    diff = create_persona_memory_diff(
        user_id=user_id,
        scope=scope,
        proposed_content=proposed_content.strip(),
        current_excerpt=current[-1200:],
        reason=reason,
        source=source,
    )
    insert_control_center_audit(
        user_id=user_id,
        action="memory_diff_proposed",
        target_type="persona_memory_diff",
        target_id=diff["id"],
        details={"scope": scope, "source": source, "reason": reason},
    )
    if auto_apply:
        return apply_memory_diff(diff["id"], reviewer_note="auto-applied")
    return diff


def get_memory_diffs(
    user_id: str,
    status: Optional[str] = None,
    limit: int = 100,
) -> dict:
    return {
        "user_id": user_id,
        "diffs": list_persona_memory_diffs(user_id=user_id, status=status, limit=limit),
    }


def approve_memory_diff(diff_id: str, reviewer_note: str = "") -> dict:
    diff = decide_persona_memory_diff(diff_id, "approved", reviewer_note)
    if diff:
        insert_control_center_audit(
            user_id=diff["user_id"],
            action="memory_diff_approved",
            target_type="persona_memory_diff",
            target_id=diff_id,
            details={"scope": diff["scope"], "reviewer_note": reviewer_note},
        )
    return diff or {"error": "not_found_or_not_pending"}


def reject_memory_diff(diff_id: str, reviewer_note: str = "") -> dict:
    diff = decide_persona_memory_diff(diff_id, "rejected", reviewer_note)
    if diff:
        insert_control_center_audit(
            user_id=diff["user_id"],
            action="memory_diff_rejected",
            target_type="persona_memory_diff",
            target_id=diff_id,
            details={"scope": diff["scope"], "reviewer_note": reviewer_note},
        )
    return diff or {"error": "not_found_or_not_pending"}


def apply_memory_diff(diff_id: str, reviewer_note: str = "") -> dict:
    diff = get_persona_memory_diff(diff_id)
    if not diff or diff["status"] not in {"pending", "approved"}:
        return {"error": "not_found_or_not_applicable"}
    updated = append_memory_entry(
        user_id=diff["user_id"],
        scope=diff["scope"],
        heading=f"Approved memory update from {diff['source']}: {_heading_fragment(diff['proposed_content'])}",
        entry=diff["proposed_content"],
        source=diff["source"],
        reason=diff["reason"],
    )
    applied = decide_persona_memory_diff(diff_id, "applied", reviewer_note)
    insert_control_center_audit(
        user_id=diff["user_id"],
        action="memory_diff_applied",
        target_type="persona_memory_diff",
        target_id=diff_id,
        details={"scope": diff["scope"], "reviewer_note": reviewer_note},
    )
    return {"status": "applied", "diff": applied, "memory": updated}


def _heading_fragment(value: str) -> str:
    clean = " ".join(str(value).split())
    return clean[:72] or "memory"
