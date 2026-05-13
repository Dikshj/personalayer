import math
import re
import time
import uuid
from typing import Any

from database import (
    delete_contextlayer_user_data,
    delete_episodic_feature_signals,
    delete_old_raw_context_events,
    demote_stale_core_feature_signals,
    get_active_context,
    get_app_permission,
    get_developer_app,
    insert_context_feedback,
    insert_pcl_query_log,
    insert_raw_context_event,
    list_contextlayer_activity,
    list_feature_signals,
    list_raw_context_events,
    log_privacy_filter_drop,
    promote_episodic_feature_signals,
    save_active_context,
    save_context_bundle_record,
    update_user_profile_record,
    update_feature_signal_scores,
    verify_developer_api_key,
)
from pcl.profile import build_local_user_context_profile


ALLOWED_EVENT_FIELDS = {
    "app_id",
    "feature_id",
    "action",
    "session_id",
    "timestamp",
    "user_id",
    "source",
    "is_synthetic",
    "metadata",
}
ALLOWED_METADATA_FIELDS = {"hour_of_day", "day_of_week", "subject_category"}
ALLOWED_ACTIONS = {"used", "skipped", "searched", "dismissed"}
ALLOWED_SOURCES = {"sdk", "extension", "connector", "onboarding"}
FEATURE_ID_RE = re.compile(r"^[a-z0-9-]+$")
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)")
CREDIT_CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
PERSONAL_UUID_RE = re.compile(r"\b[a-f0-9]{8}-[a-f0-9]{4}-[1-5][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}\b", re.IGNORECASE)


STEP_BACK_PROFILING_PROMPT = """System: You extract behavioral profile attributes from usage data. Be specific and inferential. Respond ONLY with valid JSON, no preamble.

User: Here is 7 days of behavioral signals for a user:
[SIGNAL_DATA_JSON]

Step back from these raw signals and infer:
1. What does this person genuinely value in software?
2. What are they consistently trying to accomplish?
3. What patterns suggest how they prefer to work?
4. What do they consistently avoid or skip?

Return a JSON array:
[
  {
    "attribute": "short descriptive label (e.g. 'power-database-user', 'keyboard-first', 'avoids-ai-features')",
    "value": "specific inferred value or behavior",
    "confidence": 0.0-1.0,
    "evidence_count": number of signals supporting this,
    "layer": "identity"|"capability"|"behavior"|"preference"
  }
]

Be specific. 'power-database-user' is better than 'uses databases'. Output only the JSON array."""


def ingest_context_event(event: dict, source: str) -> dict:
    candidate = {key: event.get(key) for key in ALLOWED_EVENT_FIELDS if key in event}
    candidate["source"] = source
    candidate.setdefault("user_id", "local_user")
    candidate.setdefault("timestamp", int(time.time() * 1000))

    ok, reason = validate_context_event(candidate, original_keys=set(event.keys()))
    if not ok:
        drop = log_privacy_filter_drop(candidate, reason)
        return {"status": "dropped", "reason": reason, "drop_id": drop["id"]}

    candidate["metadata"] = normalize_context_metadata(candidate.get("metadata"), candidate["timestamp"])
    update_user_profile_record(candidate["user_id"])
    saved = insert_raw_context_event(candidate)
    return {"status": "ok", "event": saved}


def normalize_context_metadata(metadata: Any, timestamp: int | None = None) -> dict[str, Any]:
    timestamp = timestamp or int(time.time() * 1000)
    local_time = time.localtime(timestamp / 1000)
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        return {
            "hour_of_day": local_time.tm_hour,
            "day_of_week": local_time.tm_wday,
        }

    normalized: dict[str, Any] = {
        "hour_of_day": int(metadata.get("hour_of_day", local_time.tm_hour)),
        "day_of_week": int(metadata.get("day_of_week", local_time.tm_wday)),
    }
    if "subject_category" in metadata:
        category = str(metadata["subject_category"]).strip().lower()
        normalized["subject_category"] = re.sub(r"[^a-z0-9_-]+", "-", category)[:80].strip("-")
    return normalized


def validate_context_event(event: dict, original_keys: set[str] | None = None) -> tuple[bool, str]:
    original_keys = original_keys or set(event.keys())
    extra_fields = original_keys - ALLOWED_EVENT_FIELDS
    if extra_fields:
        return False, f"unknown_fields:{','.join(sorted(extra_fields))}"

    for field in ("app_id", "feature_id", "action", "user_id"):
        if not str(event.get(field, "")).strip():
            return False, f"missing_{field}"

    if event["action"] not in ALLOWED_ACTIONS:
        return False, "invalid_action"
    if event.get("source") not in ALLOWED_SOURCES:
        return False, "invalid_source"
    if not FEATURE_ID_RE.match(str(event["feature_id"])):
        return False, "invalid_feature_id"
    if not isinstance(event.get("metadata", {}), dict):
        return False, "invalid_metadata"
    extra_metadata = set(event.get("metadata", {}).keys()) - ALLOWED_METADATA_FIELDS
    if extra_metadata:
        return False, f"unknown_metadata_fields:{','.join(sorted(extra_metadata))}"
    hour = event.get("metadata", {}).get("hour_of_day")
    day = event.get("metadata", {}).get("day_of_week")
    if hour is not None and not (0 <= int(hour) <= 23):
        return False, "invalid_metadata_hour"
    if day is not None and not (0 <= int(day) <= 6):
        return False, "invalid_metadata_day"

    for key, value in event.items():
        if key == "metadata":
            values = value.values()
        else:
            values = [value]
        for item in values:
            if not isinstance(item, str):
                continue
            if len(item) > 100:
                return False, f"field_too_long:{key}"
            if EMAIL_RE.search(item) or PHONE_RE.search(item) or CREDIT_CARD_RE.search(item) or PERSONAL_UUID_RE.search(item):
                return False, f"pii_detected:{key}"
    return True, ""


def build_context_bundle(
    user_id: str,
    app_id: str,
    intent: str = "full_profile",
    requested_scopes: list[str] | None = None,
    source: str = "rest",
) -> dict:
    from pcl.daily_refresh import queue_urgent_synthesis, should_mark_bundle_stale

    permission = get_app_permission(user_id, app_id)
    if permission and not permission["is_active"]:
        return {
            "error": "app_consent_revoked",
            "app_id": app_id,
            "user_id": user_id,
            "features": [],
            "suppressed_features": [],
            "confidence": 0.0,
            "stale": should_mark_bundle_stale(user_id),
        }

    boundary = resolve_intent_boundary(intent)
    signals = list_feature_signals(user_id=user_id, app_id=app_id) if boundary["includesLayer2"] else []
    profile = build_local_user_context_profile(user_id) if boundary["includesLayer1"] else None
    active_context = get_active_context(user_id) if boundary["includesLayer4"] else None

    featured = [
        signal["feature_id"]
        for signal in signals
        if float(signal["recency_score"]) > boundary["featureThreshold"]
    ]
    suppressed = [
        signal["feature_id"]
        for signal in signals
        if float(signal["recency_score"]) < boundary["suppressThreshold"]
        and int(signal["usage_count"]) > 0
    ]
    confidence = (
        sum(float(signal["recency_score"]) for signal in signals if signal["feature_id"] in featured) / len(featured)
        if featured else 0.0
    )
    bundle_id = str(uuid.uuid4())
    expires_at = int(time.time() * 1000) + 3_600_000
    save_context_bundle_record(bundle_id, user_id, app_id, featured, expires_at)
    insert_pcl_query_log(
        app_id=app_id,
        user_id=user_id,
        purpose=intent,
        requested_layers=requested_scopes or [],
        returned_layers=_returned_layers(boundary),
        feature_ids=featured,
        status="returned",
    )

    stale = should_mark_bundle_stale(user_id)
    urgent_job = queue_urgent_synthesis(user_id) if stale else None

    return {
        "bundle_id": bundle_id,
        "stale": stale,
        "urgent_synthesis_job_id": urgent_job["id"] if urgent_job else None,
        "features": featured,
        "suppressed_features": suppressed,
        "style": infer_style(profile),
        "timing": infer_timing(),
        "constraints": build_constraints(profile),
        "active_context": active_context or (profile.active_context.model_dump() if profile and boundary["includesLayer4"] else None),
        "abstract_attributes": profile.meta.get("abstract_attributes", []) if profile else [],
        "confidence": round(confidence, 2),
        "expires_at": expires_at,
        "permission": {
            "status": "granted" if permission and permission["is_active"] else "local_default",
            "scopes": permission["scopes"] if permission else [],
        },
    }


def authorize_developer_context_request(
    authorization: str,
    user_id: str,
    app_id: str,
    requested_scopes: list[str] | None = None,
) -> dict:
    raw_key = _bearer_token(authorization)
    if not raw_key:
        return {"authorized": True, "mode": "local_default"}
    key = verify_developer_api_key(raw_key)
    if not key:
        return {"authorized": False, "error": "invalid_developer_api_key"}
    if key["app_id"] and key["app_id"] != app_id:
        return {"authorized": False, "error": "api_key_app_mismatch"}
    app = get_developer_app(app_id)
    if app and key["developer_id"] != app["developer_id"]:
        return {"authorized": False, "error": "developer_app_mismatch"}
    permission = get_app_permission(user_id, app_id)
    if not permission or not permission["is_active"]:
        return {"authorized": False, "error": "missing_user_consent"}
    missing_scopes = sorted(set(requested_scopes or []) - set(permission["scopes"]))
    if missing_scopes:
        return {
            "authorized": False,
            "error": "scope_not_granted",
            "missing_scopes": missing_scopes,
            "granted_scopes": permission["scopes"],
        }
    return {
        "authorized": True,
        "mode": "developer",
        "developer_id": key["developer_id"],
        "api_key_id": key["id"],
        "scopes": permission["scopes"],
    }


def resolve_intent_boundary(intent: str | None) -> dict[str, Any]:
    if not intent or intent == "full_profile":
        return _boundary(True, True, True, True, True, 0.1, 0.2)
    if "suggest_features" in intent or "adapt_ui" in intent:
        return _boundary(False, True, False, False, True, 0.3, 0.1)
    if "onboarding" in intent:
        return _boundary(True, True, False, False, True, 0.0, 0.5)
    if "constraints" in intent or "preferences" in intent:
        return _boundary(False, False, False, False, True, 0.0, 0.0)
    return _boundary(True, True, False, True, True, 0.2, 0.15)


def apply_context_feedback(
    user_id: str,
    bundle_id: str,
    app_id: str,
    outcome: str,
    features_actually_used: list[str],
) -> dict:
    feedback = insert_context_feedback(
        user_id=user_id,
        bundle_id=bundle_id,
        app_id=app_id,
        outcome=outcome,
        features_actually_used=features_actually_used,
    )
    return {"status": "ok", "feedback": feedback}


def update_active_context(
    user_id: str,
    project: str = "",
    active_apps: list[str] | None = None,
    inferred_intent: str = "",
    session_depth: str = "shallow",
) -> dict:
    context = save_active_context(
        user_id=user_id,
        project=project,
        active_apps=active_apps or [],
        inferred_intent=inferred_intent,
        session_depth=session_depth,
    )
    return {"status": "ok", "active_context": context}


def get_contextlayer_activity(user_id: str, limit: int = 100) -> dict:
    return {"user_id": user_id, **list_contextlayer_activity(user_id=user_id, limit=limit)}


def hard_delete_contextlayer_user(user_id: str) -> dict:
    return {"status": "deleted", **delete_contextlayer_user_data(user_id)}


def run_decay_engine(now_ms: int | None = None, user_id: str | None = None) -> dict:
    now_ms = now_ms or int(time.time() * 1000)
    updates: list[tuple[str, float, float, int]] = []
    delete_ids: list[str] = []
    user_ids = [user_id] if user_id else _active_user_ids()
    for current_user_id in user_ids:
        for signal in list_feature_signals(user_id=current_user_id, active_only=False):
            days_since = max(0.0, (now_ms - int(signal["last_used_at"] or now_ms)) / 86_400_000)
            lam = 0.02 if signal["tier"] == "core" else 0.12
            decayed = max(0.0, float(signal["recency_score"]) * math.exp(-lam * days_since))
            is_active = 0 if decayed < 0.05 else 1
            if decayed < 0.01 and signal["tier"] == "episodic":
                delete_ids.append(signal["id"])
            else:
                updates.append((signal["id"], round(decayed, 4), round(decayed, 4), is_active))
    update_feature_signal_scores(updates)
    deleted = delete_episodic_feature_signals(delete_ids)
    return {"updated": len(updates), "deleted": deleted}


def run_inductive_memory_job() -> dict:
    return {"promoted": promote_episodic_feature_signals()}


def run_reflective_memory_job() -> dict:
    return {"demoted": demote_stale_core_feature_signals()}


def run_profile_synthesizer() -> dict:
    # Local deterministic distillation. The production implementation should use
    # STEP_BACK_PROFILING_PROMPT with claude-sonnet-4-20250514.
    touched = 0
    for user_id in _active_user_ids():
        result = run_profile_synthesizer_for_user(user_id)
        if result["events_read"]:
            touched += 1
    return {"users_synthesized": touched, "prompt_template": STEP_BACK_PROFILING_PROMPT}


def run_profile_synthesizer_for_user(user_id: str) -> dict:
    # Local deterministic distillation. Production should call the LLM prompt
    # above and merge JSON attributes into feature_signals.abstract_attributes.
    events = list_raw_context_events(user_id, days=7)
    attributes: list[dict[str, Any]] = []
    if events:
        by_feature: dict[str, int] = {}
        for event in events:
            key = f"{event['app_id']}:{event['feature_id']}"
            by_feature[key] = by_feature.get(key, 0) + 1
        top_key, count = sorted(by_feature.items(), key=lambda item: item[1], reverse=True)[0]
        attributes.append({
            "attribute": f"recent-{top_key.replace(':', '-')}-user",
            "value": f"Repeated use of {top_key} over the last 7 days",
            "confidence": min(0.95, 0.55 + count * 0.05),
            "evidence_count": count,
            "layer": "capability",
        })
    now_ms = int(time.time() * 1000)
    update_user_profile_record(
        user_id,
        abstract_attributes=attributes,
        last_synthesized_at=now_ms,
    )
    return {
        "user_id": user_id,
        "events_read": len(events),
        "attributes": attributes,
        "last_synthesized_at": now_ms,
        "prompt_template": STEP_BACK_PROFILING_PROMPT,
    }


def infer_style(profile: Any) -> str | None:
    if not profile:
        return None
    workflow = (profile.behavior.workflow_style or "").lower()
    if "minimal" in workflow or "quick" in workflow:
        return "compact"
    if "guided" in workflow:
        return "guided"
    return "detailed" if workflow else None


def infer_timing() -> str:
    hour = time.localtime().tm_hour
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    return "evening"


def build_constraints(profile: Any) -> dict[str, Any]:
    if not profile:
        return {}
    return {
        pref.key: pref.value
        for pref in profile.explicit_preferences
        if pref.hard_rule
    }


def _boundary(
    includes_layer1: bool,
    includes_layer2: bool,
    includes_layer3: bool,
    includes_layer4: bool,
    includes_layer5: bool,
    feature_threshold: float,
    suppress_threshold: float,
) -> dict[str, Any]:
    return {
        "includesLayer1": includes_layer1,
        "includesLayer2": includes_layer2,
        "includesLayer3": includes_layer3,
        "includesLayer4": includes_layer4,
        "includesLayer5": includes_layer5,
        "featureThreshold": feature_threshold,
        "suppressThreshold": suppress_threshold,
    }


def _returned_layers(boundary: dict[str, Any]) -> list[str]:
    mapping = {
        "includesLayer1": "identity_role",
        "includesLayer2": "capability_signals",
        "includesLayer3": "behavior_patterns",
        "includesLayer4": "active_context",
        "includesLayer5": "explicit_preferences",
    }
    return [layer for key, layer in mapping.items() if boundary.get(key)]


def _active_user_ids() -> list[str]:
    # SQLite local prototype: derive active users from feature signals by scanning
    # through known queryable users instead of maintaining a separate auth table.
    from database import get_connection

    with get_connection() as conn:
        rows = conn.execute("SELECT DISTINCT user_id FROM feature_signals").fetchall()
    return [row["user_id"] for row in rows]


def _bearer_token(authorization: str) -> str:
    value = (authorization or "").strip()
    if not value:
        return ""
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return value
