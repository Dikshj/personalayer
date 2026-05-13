import time
from datetime import datetime
from typing import Any

from database import (
    get_pcl_integration,
    insert_feed_item,
    insert_persona_signal,
    list_pcl_integrations,
    update_pcl_integration_sync,
)
from pcl.integrations import default_integration
from pcl.privacy import scrub_pii


def sync_integration(source: str, user_id: str = "local_user") -> dict:
    try:
        default_integration(source)
    except ValueError:
        return {"status": "error", "error": "unknown_integration"}

    integration = get_pcl_integration(source)
    if not integration or integration.get("status") != "connected":
        return {"status": "error", "error": "integration_not_connected"}

    syncers = {
        "gmail": _sync_gmail,
        "calendar": _sync_calendar,
        "notion": _sync_notion,
        "github": _sync_github,
        "spotify": _sync_spotify,
        "youtube": _sync_youtube,
        "apple_health": _sync_apple_health,
    }
    return syncers[source](integration, user_id=user_id)


def sync_connected_integrations(user_id: str = "local_user") -> dict:
    results = []
    for integration in list_pcl_integrations():
        if integration.get("status") != "connected":
            continue
        metadata_user_id = str(integration.get("metadata", {}).get("user_id", user_id))
        if metadata_user_id != user_id:
            continue
        results.append(sync_integration(integration["source"], user_id=user_id))
    return {
        "synced": sum(1 for result in results if result.get("status") == "ok"),
        "attempted": len(results),
        "items_synced": sum(int(result.get("items_synced", 0) or 0) for result in results),
        "results": results,
    }


def _metadata_items(metadata: dict, *keys: str) -> list[dict]:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _timestamp_ms(value: Any = None) -> int:
    if isinstance(value, (int, float)):
        if value < 10_000_000_000:
            return int(value * 1000)
        return int(value)
    if isinstance(value, str) and value.strip():
        raw = value.strip()
        try:
            if raw.isdigit():
                return _timestamp_ms(int(raw))
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return int(parsed.timestamp() * 1000)
        except ValueError:
            pass
    return int(time.time() * 1000)


def _hour_bucket(timestamp_ms: int) -> str:
    hour = datetime.fromtimestamp(timestamp_ms / 1000).hour
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 22:
        return "evening"
    return "late_night"


def _finish_sync(source: str, count: int, status: str = "ok", error: str = "") -> dict:
    updated = update_pcl_integration_sync(
        source=source,
        status=status,
        items_synced=count,
        error=error,
    )
    return {"status": status, "items_synced": count, "integration": updated}


def _missing_payload(source: str, expected: str) -> dict:
    updated = update_pcl_integration_sync(
        source=source,
        status="error",
        items_synced=0,
        error=f"Import metadata required: {expected}",
    )
    return {
        "status": "error",
        "error": "import_metadata_required",
        "expected": expected,
        "integration": updated,
    }


def _sync_gmail(integration: dict, user_id: str = "local_user") -> dict:
    metadata = integration.get("metadata", {})
    messages = _metadata_items(metadata, "messages", "emails", "threads", "import_items")
    if not messages:
        return _missing_payload("gmail", "metadata.messages[]")

    saved = 0
    for message in messages:
        ts = _timestamp_ms(message.get("timestamp") or message.get("date"))
        labels = [
            str(label).strip().lower()
            for label in message.get("labels", [])
            if str(label).strip()
        ]
        sender_domain = (
            message.get("sender_domain")
            or str(message.get("from", "")).split("@")[-1].split(">")[0]
        ).strip().lower()
        content = {
            "kind": "email_metadata",
            "labels": labels[:8],
            "sender_domain": sender_domain[:120],
            "thread_size": int(message.get("thread_size", 1) or 1),
            "has_attachments": bool(message.get("has_attachments", False)),
            "hour_bucket": _hour_bucket(ts),
        }
        insert_feed_item(
            source="gmail",
            content_type="email_metadata",
            content=str(scrub_pii(content)),
            author=sender_domain,
            url="",
            timestamp=ts,
        )
        for label in labels[:5]:
            insert_persona_signal(
                source="gmail",
                signal_type="communication_label",
                name=f"email_label:{label}",
                weight=1.0,
                confidence=0.65,
                evidence="Imported Gmail label metadata",
                timestamp=ts,
            )
        if content["has_attachments"]:
            insert_persona_signal(
                source="gmail",
                signal_type="workflow_pattern",
                name="attachment_heavy_email",
                weight=0.7,
                confidence=0.55,
                evidence="Imported Gmail attachment metadata",
                timestamp=ts,
            )
            _emit_connector_event(
                user_id=user_id,
                app_id="gmail",
                feature_id="attachment-heavy-email",
                timestamp=ts,
                subject_category="email",
            )
        for label in labels[:5]:
            _emit_connector_event(
                user_id=user_id,
                app_id="gmail",
                feature_id=f"label-{_feature_token(label)}",
                timestamp=ts,
                subject_category="email",
            )
        if content["thread_size"] >= 3:
            _emit_connector_event(
                user_id=user_id,
                app_id="gmail",
                feature_id="multi-message-thread",
                timestamp=ts,
                subject_category="email",
            )
        saved += 1

    return _finish_sync("gmail", saved)


def _sync_calendar(integration: dict, user_id: str = "local_user") -> dict:
    metadata = integration.get("metadata", {})
    events = _metadata_items(metadata, "events", "meetings", "import_items")
    if not events:
        return _missing_payload("calendar", "metadata.events[]")

    saved = 0
    for event in events:
        ts = _timestamp_ms(event.get("start") or event.get("timestamp"))
        duration = max(0, int(event.get("duration_minutes", 0) or 0))
        attendees = max(0, int(event.get("attendee_count", 0) or 0))
        content = {
            "kind": "calendar_event_metadata",
            "duration_minutes": duration,
            "attendee_count": attendees,
            "hour_bucket": _hour_bucket(ts),
            "status": str(event.get("status", "confirmed"))[:80],
        }
        insert_feed_item(
            source="calendar",
            content_type="event_metadata",
            content=str(scrub_pii(content)),
            author="calendar",
            url="",
            timestamp=ts,
        )
        if duration >= 45:
            insert_persona_signal(
                source="calendar",
                signal_type="meeting_pattern",
                name="long_meetings",
                weight=min(duration / 60, 3.0),
                confidence=0.7,
                evidence="Imported calendar duration metadata",
                timestamp=ts,
            )
            _emit_connector_event(
                user_id=user_id,
                app_id="calendar",
                feature_id="long-meeting",
                timestamp=ts,
                subject_category="meeting",
            )
        if attendees >= 3:
            insert_persona_signal(
                source="calendar",
                signal_type="collaboration_pattern",
                name="group_meetings",
                weight=min(attendees / 4, 3.0),
                confidence=0.65,
                evidence="Imported calendar attendee metadata",
                timestamp=ts,
            )
            _emit_connector_event(
                user_id=user_id,
                app_id="calendar",
                feature_id="group-meeting",
                timestamp=ts,
                subject_category="meeting",
            )
        saved += 1

    return _finish_sync("calendar", saved)


def _sync_notion(integration: dict, user_id: str = "local_user") -> dict:
    metadata = integration.get("metadata", {})
    pages = _metadata_items(metadata, "pages", "page_activity", "import_items")
    if not pages:
        return _missing_payload("notion", "metadata.pages[]")

    saved = 0
    for page in pages:
        ts = _timestamp_ms(page.get("last_edited_time") or page.get("timestamp"))
        object_type = str(page.get("object_type", page.get("type", "page")))[:80]
        workspace = str(page.get("workspace", ""))[:120]
        tags = [str(tag).strip().lower() for tag in page.get("tags", []) if str(tag).strip()]
        content = {
            "kind": "notion_page_activity",
            "object_type": object_type,
            "workspace": workspace,
            "tags": tags[:8],
            "hour_bucket": _hour_bucket(ts),
        }
        insert_feed_item(
            source="notion",
            content_type="page_activity",
            content=str(scrub_pii(content)),
            author=workspace,
            url="",
            timestamp=ts,
        )
        insert_persona_signal(
            source="notion",
            signal_type="knowledge_work_tool",
            name=f"notion_{object_type}",
            weight=1.0,
            confidence=0.65,
            evidence="Imported Notion activity metadata",
            timestamp=ts,
        )
        _emit_connector_event(
            user_id=user_id,
            app_id="notion",
            feature_id=f"{_feature_token(object_type)}-activity",
            timestamp=ts,
            subject_category="knowledge-work",
        )
        for tag in tags[:5]:
            insert_persona_signal(
                source="notion",
                signal_type="project_topic",
                name=f"notion_tag:{tag}",
                weight=0.8,
                confidence=0.6,
                evidence="Imported Notion tag metadata",
                timestamp=ts,
            )
            _emit_connector_event(
                user_id=user_id,
                app_id="notion",
                feature_id=f"tag-{_feature_token(tag)}",
                timestamp=ts,
                subject_category="knowledge-work",
            )
        saved += 1

    return _finish_sync("notion", saved)


def _sync_github(integration: dict, user_id: str = "local_user") -> dict:
    metadata = integration.get("metadata", {})
    username = (
        metadata.get("username")
        or metadata.get("github_username")
        or metadata.get("account_hint")
        or ""
    ).strip()
    if not username:
        updated = update_pcl_integration_sync(
            source="github",
            status="error",
            items_synced=0,
            error="GitHub username required in integration metadata",
        )
        return {"status": "error", "error": "username_required", "integration": updated}

    try:
        from collectors.github import collect_github
        count = collect_github(username)
    except Exception as exc:
        updated = update_pcl_integration_sync(
            source="github",
            status="error",
            items_synced=0,
            error=str(exc),
        )
        return {"status": "error", "error": str(exc), "integration": updated}

    updated = update_pcl_integration_sync(
        source="github",
        status="ok",
        items_synced=count,
        error="",
    )
    return {"status": "ok", "items_synced": count, "integration": updated}


def _sync_spotify(integration: dict, user_id: str = "local_user") -> dict:
    metadata = integration.get("metadata", {})
    plays = _metadata_items(metadata, "recently_played", "plays", "sessions", "import_items")
    if not plays:
        return _missing_payload("spotify", "metadata.recently_played[]")

    saved = 0
    for play in plays:
        ts = _timestamp_ms(play.get("played_at") or play.get("timestamp"))
        duration = max(0, int(play.get("duration_minutes", 0) or play.get("session_minutes", 0) or 0))
        genres = [str(genre).strip().lower() for genre in play.get("genres", []) if str(genre).strip()]
        content = {
            "kind": "spotify_session_metadata",
            "duration_minutes": duration,
            "genres": genres[:5],
            "hour_bucket": _hour_bucket(ts),
        }
        insert_feed_item(
            source="spotify",
            content_type="session_metadata",
            content=str(scrub_pii(content)),
            author="spotify",
            url="",
            timestamp=ts,
        )
        if duration >= 30:
            insert_persona_signal(
                source="spotify",
                signal_type="focus_pattern",
                name="long_focus_audio_session",
                weight=min(duration / 45, 3.0),
                confidence=0.55,
                evidence="Imported Spotify session metadata",
                timestamp=ts,
            )
            _emit_connector_event(
                user_id=user_id,
                app_id="spotify",
                feature_id="long-focus-session",
                timestamp=ts,
                subject_category="focus",
            )
        for genre in genres[:3]:
            _emit_connector_event(
                user_id=user_id,
                app_id="spotify",
                feature_id=f"genre-{_feature_token(genre)}",
                timestamp=ts,
                subject_category="focus",
            )
        saved += 1

    return _finish_sync("spotify", saved)


def _sync_youtube(integration: dict, user_id: str = "local_user") -> dict:
    metadata = integration.get("metadata", {})
    videos = _metadata_items(metadata, "watch_history", "videos", "sessions", "import_items")
    if not videos:
        return _missing_payload("youtube", "metadata.watch_history[]")

    saved = 0
    for video in videos:
        ts = _timestamp_ms(video.get("watched_at") or video.get("timestamp"))
        category = _feature_token(video.get("category", video.get("topic", "video")))
        duration = max(0, int(video.get("duration_minutes", 0) or 0))
        content = {
            "kind": "youtube_watch_metadata",
            "category": category,
            "duration_minutes": duration,
            "hour_bucket": _hour_bucket(ts),
        }
        insert_feed_item(
            source="youtube",
            content_type="watch_metadata",
            content=str(scrub_pii(content)),
            author="youtube",
            url="",
            timestamp=ts,
        )
        insert_persona_signal(
            source="youtube",
            signal_type="learning_pattern",
            name=f"youtube_category:{category}",
            weight=1.0,
            confidence=0.55,
            evidence="Imported YouTube watch metadata",
            timestamp=ts,
        )
        _emit_connector_event(
            user_id=user_id,
            app_id="youtube",
            feature_id=f"category-{category}",
            timestamp=ts,
            subject_category="learning",
        )
        if duration >= 20:
            _emit_connector_event(
                user_id=user_id,
                app_id="youtube",
                feature_id="long-watch-session",
                timestamp=ts,
                subject_category="learning",
            )
        saved += 1

    return _finish_sync("youtube", saved)


def _sync_apple_health(integration: dict, user_id: str = "local_user") -> dict:
    metadata = integration.get("metadata", {})
    samples = _metadata_items(metadata, "activity", "daily_activity", "samples", "import_items")
    if not samples:
        return _missing_payload("apple_health", "metadata.activity[]")

    saved = 0
    for sample in samples:
        ts = _timestamp_ms(sample.get("date") or sample.get("timestamp"))
        active_minutes = max(0, int(sample.get("active_minutes", 0) or 0))
        stand_hours = max(0, int(sample.get("stand_hours", 0) or 0))
        sleep_hours = max(0.0, float(sample.get("sleep_hours", 0) or 0))
        content = {
            "kind": "apple_health_activity_metadata",
            "active_minutes": active_minutes,
            "stand_hours": stand_hours,
            "sleep_hours": sleep_hours,
            "hour_bucket": _hour_bucket(ts),
        }
        insert_feed_item(
            source="apple_health",
            content_type="activity_metadata",
            content=str(scrub_pii(content)),
            author="apple_health",
            url="",
            timestamp=ts,
        )
        if active_minutes >= 30:
            insert_persona_signal(
                source="apple_health",
                signal_type="energy_pattern",
                name="active_day",
                weight=min(active_minutes / 45, 3.0),
                confidence=0.55,
                evidence="Imported Apple Health activity metadata",
                timestamp=ts,
            )
            _emit_connector_event(
                user_id=user_id,
                app_id="apple-health",
                feature_id="active-day",
                timestamp=ts,
                subject_category="health",
            )
        if sleep_hours and sleep_hours < 6:
            _emit_connector_event(
                user_id=user_id,
                app_id="apple-health",
                feature_id="short-sleep",
                timestamp=ts,
                subject_category="health",
            )
        elif sleep_hours >= 7:
            _emit_connector_event(
                user_id=user_id,
                app_id="apple-health",
                feature_id="recovered-sleep",
                timestamp=ts,
                subject_category="health",
            )
        saved += 1

    return _finish_sync("apple_health", saved)


def _emit_connector_event(
    user_id: str,
    app_id: str,
    feature_id: str,
    timestamp: int,
    subject_category: str = "",
) -> bool:
    from pcl.contextlayer import ingest_context_event

    event = {
        "user_id": user_id,
        "app_id": app_id,
        "feature_id": _feature_token(feature_id),
        "action": "used",
        "session_id": f"connector-{app_id}",
        "timestamp": timestamp,
        "metadata": {
            "hour_of_day": datetime.fromtimestamp(timestamp / 1000).hour,
            "day_of_week": datetime.fromtimestamp(timestamp / 1000).weekday(),
        },
    }
    if subject_category:
        event["metadata"]["subject_category"] = _feature_token(subject_category)
    result = ingest_context_event(event, source="connector")
    return result.get("status") == "ok"


def _feature_token(value: Any) -> str:
    token = "".join(
        char if char.isalnum() else "-"
        for char in str(value).strip().lower()
    )
    while "--" in token:
        token = token.replace("--", "-")
    return token.strip("-")[:80] or "unknown"
