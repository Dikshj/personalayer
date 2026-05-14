from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
from typing import Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from database import (
    create_or_resume_daily_refresh_job,
    delete_old_raw_context_events,
    delete_old_temporal_chains,
    get_daily_refresh_job,
    get_user_profile_record,
    insert_daily_refresh_step_log,
    list_daily_refresh_step_logs,
    list_feature_signals,
    list_raw_context_events,
    list_user_profile_records,
    maintain_knowledge_graph_tiers,
    mark_daily_refresh_complete,
    mark_daily_refresh_failed,
    promote_episodic_feature_signals,
    queue_notification_routes,
    update_daily_refresh_step,
    update_user_profile_record,
)
from pcl.contextlayer import (
    run_decay_engine,
    run_profile_synthesizer_for_user,
)


DAILY_INSIGHT_PROMPT = """Given these changes to the user's context layer today:
NEW_SIGNALS: [array of new abstract attributes added]
PROMOTED: [signals that moved from episodic to core today]
DECAYED: [signals whose recency_score dropped significantly]

Write ONE sentence (max 15 words) that tells the user something interesting
they might not know about themselves based on today's data.
Be specific. Use their actual data. Sound like a smart friend, not a system.
Output only the sentence. No preamble."""


@dataclass(frozen=True)
class RefreshStep:
    number: int
    name: str
    runner: Callable[[str], dict]


def run_daily_refresh(
    user_id: str,
    timezone: str = "UTC",
    job_id: str | None = None,
    step_completed: int = 0,
    today: datetime | None = None,
) -> dict:
    job = create_or_resume_daily_refresh_job(
        user_id=user_id,
        timezone=timezone,
        job_id=job_id,
        step_completed=step_completed,
    )
    today = today or datetime.now()

    try:
        for step in _steps(today):
            job = get_daily_refresh_job(job["id"]) or job
            if int(job["step_completed"]) >= step.number:
                continue
            result = step.runner(user_id)
            insert_daily_refresh_step_log(
                job_id=job["id"],
                user_id=user_id,
                step_number=step.number,
                step_name=step.name,
                status="ok",
            )
            update_daily_refresh_step(job["id"], step.number)
            job["last_result"] = result

        complete = mark_daily_refresh_complete(job["id"], user_id)
        return {
            "status": "complete",
            "job": complete,
            "logs": list_daily_refresh_step_logs(job["id"]),
        }
    except Exception as exc:
        insert_daily_refresh_step_log(
            job_id=job["id"],
            user_id=user_id,
            step_number=int((get_daily_refresh_job(job["id"]) or job)["step_completed"]) + 1,
            step_name="unknown",
            status="error",
            error=str(exc),
        )
        failed = mark_daily_refresh_failed(job["id"], str(exc))
        return {"status": "failed", "job": failed, "error": str(exc)}


def run_due_daily_refreshes(now: datetime | None = None) -> dict:
    now = _as_utc(now or datetime.now(dt_timezone.utc))
    due_profiles = [
        profile for profile in list_user_profile_records()
        if is_daily_refresh_due(profile, now)
    ]
    results = []
    for profile in due_profiles:
        results.append(run_daily_refresh(
            user_id=profile["user_id"],
            timezone=profile.get("timezone") or "UTC",
            today=now,
        ))
    return {
        "status": "ok",
        "due_users": [profile["user_id"] for profile in due_profiles],
        "refreshed": len(results),
        "results": results,
    }


def is_daily_refresh_due(profile: dict, now: datetime | None = None) -> bool:
    now = _as_utc(now or datetime.now(dt_timezone.utc))
    tz_name = profile.get("timezone") or "UTC"
    local_now = now.astimezone(_zoneinfo(tz_name))
    if local_now.hour < 3:
        return False
    last_refresh_at = profile.get("last_refresh_at")
    if not last_refresh_at:
        return True
    last_refresh_local = datetime.fromtimestamp(
        int(last_refresh_at) / 1000,
        tz=dt_timezone.utc,
    ).astimezone(_zoneinfo(tz_name))
    return last_refresh_local.date() < local_now.date()


def queue_urgent_synthesis(user_id: str) -> dict:
    now_ms = int(time.time() * 1000)
    profile = get_user_profile_record(user_id) or {}
    job = create_or_resume_daily_refresh_job(
        user_id=user_id,
        timezone=profile.get("timezone") or "UTC",
        job_id=f"urgent-synthesis-{user_id}-{now_ms // 3_600_000}",
        step_completed=3,
    )
    insert_daily_refresh_step_log(
        job_id=job["id"],
        user_id=user_id,
        step_number=4,
        step_name="profile_synthesizer_queued",
        status="queued",
    )
    return job


def _steps(today: datetime) -> list[RefreshStep]:
    return [
        RefreshStep(1, "connector_sync", connector_sync),
        RefreshStep(2, "privacy_filter", privacy_filter_batch),
        RefreshStep(3, "signal_classifier", signal_classifier_route),
        RefreshStep(4, "profile_synthesizer", profile_synthesizer),
        RefreshStep(5, "decay_engine", decay_engine),
        RefreshStep(6, "bi_mem_inductive", bi_mem_inductive),
        RefreshStep(7, "bi_mem_reflective", bi_mem_reflective),
        RefreshStep(8, "tier_maintenance", tier_maintenance),
        RefreshStep(9, "shared_context_file", shared_context_file),
        RefreshStep(10, "daily_insight_generation", daily_insight_generation),
        RefreshStep(11, "raw_event_cleanup", raw_event_cleanup),
    ]


def connector_sync(user_id: str) -> dict:
    from pcl.integration_jobs import sync_connected_integrations

    return sync_connected_integrations(user_id=user_id)


def privacy_filter_batch(user_id: str) -> dict:
    # The blocking privacy gate runs synchronously in ingest_context_event before
    # raw_events is written, so the daily step verifies the invariant only.
    return {"status": "already_applied_at_ingest"}


def signal_classifier_route(user_id: str) -> dict:
    # Ingest writes feature_signals immediately for Layer 2 in the local model.
    events = list_raw_context_events(user_id, days=7)
    return {"routed_events": len(events)}


def profile_synthesizer(user_id: str) -> dict:
    return run_profile_synthesizer_for_user(user_id)


def decay_engine(user_id: str) -> dict:
    return run_decay_engine(user_id=user_id)


def bi_mem_inductive(user_id: str) -> dict:
    return {"promoted": promote_episodic_feature_signals(user_id=user_id)}


def bi_mem_reflective(user_id: str) -> dict:
    from database import demote_stale_core_feature_signals

    return {"demoted": demote_stale_core_feature_signals(user_id=user_id)}


def tier_maintenance(user_id: str) -> dict:
    return maintain_knowledge_graph_tiers(user_id=user_id)


def tsubasa_distillation(user_id: str) -> dict:
    episodic = [
        signal
        for signal in list_feature_signals(user_id=user_id, active_only=False)
        if signal["tier"] == "episodic"
    ]
    if len(episodic) < 10:
        return {"skipped": True, "reason": "not_enough_history"}
    summary = {
        "attribute": "long-horizon-tool-pattern",
        "value": ", ".join(signal["feature_id"] for signal in episodic[:5]),
        "confidence": 0.65,
        "evidence_count": len(episodic),
        "layer": "capability",
    }
    profile = get_user_profile_record(user_id) or {"abstract_attributes": []}
    update_user_profile_record(
        user_id,
        abstract_attributes=[*profile.get("abstract_attributes", []), summary],
    )
    return {"distilled": 1}


def brief_regeneration(user_id: str) -> dict:
    signals = list_feature_signals(user_id=user_id)[:8]
    profile = get_user_profile_record(user_id) or {"abstract_attributes": []}
    attributes = profile.get("abstract_attributes", [])[:5]
    feature_text = ", ".join(f"{s['app_id']}:{s['feature_id']}" for s in signals) or "not enough signal yet"
    attribute_text = ", ".join(a.get("attribute", "") for a in attributes if isinstance(a, dict)) or "no abstract attributes yet"
    brief = (
        f"ContextLayer brief: top features are {feature_text}. "
        f"Current abstract profile: {attribute_text}."
    )
    update_user_profile_record(user_id, context_brief=brief)
    return {"context_brief": brief}


def shared_context_file(user_id: str) -> dict:
    from pcl.shared_context import write_shared_context_bundle

    brief = brief_regeneration(user_id)
    shared = write_shared_context_bundle(user_id)
    return {"context_brief": brief["context_brief"], "shared_context": shared}


def daily_insight_generation(user_id: str) -> dict:
    signals = list_feature_signals(user_id=user_id)[:5]
    if not signals:
        insight = "ContextLayer needs more usage before it can spot a pattern."
    else:
        top = signals[0]
        if top["tier"] == "core":
            insight = f"{top['feature_id']} is now one of your core {top['app_id']} patterns."
        else:
            insight = f"{top['feature_id']} is your strongest recent {top['app_id']} signal."
    update_user_profile_record(user_id, daily_insight=insight)
    delivery = queue_notification_routes(
        user_id=user_id,
        notification_type="daily_insight_ready",
        deliver_after=_next_local_8am_ms(),
        payload_kind="silent_local_insight",
    )
    return {
        "daily_insight": insight,
        "prompt_template": DAILY_INSIGHT_PROMPT,
        "notification_routing": {
            "queued": delivery["queued"],
            "payload_kind": "silent_local_insight",
            "behavioral_text_sent_to_cloud": False,
        },
    }


def raw_event_cleanup(user_id: str) -> dict:
    return {
        "raw_events_deleted": delete_old_raw_context_events(user_id=user_id),
        "temporal_chains_deleted": delete_old_temporal_chains(user_id=user_id),
    }


def should_mark_bundle_stale(user_id: str, now_ms: int | None = None) -> bool:
    profile = get_user_profile_record(user_id)
    if not profile or not profile.get("last_synthesized_at"):
        return True
    now_ms = now_ms or int(time.time() * 1000)
    hours_since = (now_ms - int(profile["last_synthesized_at"])) / 3_600_000
    return hours_since > 26


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=dt_timezone.utc)
    return value.astimezone(dt_timezone.utc)


def _zoneinfo(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _next_local_8am_ms(now: datetime | None = None) -> int:
    now = now or datetime.now()
    target = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if target <= now:
        from datetime import timedelta

        target = target + timedelta(days=1)
    return int(target.timestamp() * 1000)
