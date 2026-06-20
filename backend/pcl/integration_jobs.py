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
from pcl.oauth import refresh_oauth_token
from pcl.persona_diffs import propose_memory_diff
from pcl.privacy import scrub_pii


def sync_integration(source: str, user_id: str = "local_user") -> dict:
    try:
        default_integration(source)
    except ValueError:
        return {"status": "error", "error": "unknown_integration"}

    integration = get_pcl_integration(source, user_id=user_id)
    if not integration or integration.get("status") != "connected":
        return {"status": "error", "error": "integration_not_connected"}
    if not _sync_due(integration):
        return {
            "status": "skipped",
            "reason": "next_sync_after_not_reached",
            "next_sync_after": integration.get("next_sync_after"),
            "integration": integration,
        }
    refresh_result = _refresh_expired_oauth_if_needed(integration, user_id=user_id)
    if refresh_result.get("status") == "error":
        return refresh_result
    if refresh_result.get("status") == "refreshed":
        integration = get_pcl_integration(source, user_id=user_id) or integration

    syncers = {
        "gmail": _sync_gmail,
        "calendar": _sync_calendar,
        "notion": _sync_notion,
        "github": _sync_github,
        "spotify": _sync_spotify,
        "youtube": _sync_youtube,
        "apple_health": _sync_apple_health,
        "google_drive": _sync_google_drive,
        "slack": _sync_slack,
        "linear": _sync_linear,
        "jira": _sync_jira,
        "todoist": _sync_todoist,
        "strava": _sync_strava,
        "reddit": _sync_reddit,
        "figma": _sync_figma,
        "dropbox": _sync_dropbox,
        "onedrive": _sync_onedrive,
        "trello": _sync_trello,
        "asana": _sync_asana,
        "linkedin": _sync_social_activity,
        "x": _sync_social_activity,
        "instagram": _sync_social_activity,
        "chatgpt": _sync_ai_activity,
        "claude": _sync_ai_activity,
        "perplexity": _sync_ai_activity,
        "opencode": _sync_dev_activity,
        "cursor": _sync_dev_activity,
        "gemini": _sync_ai_activity,
        "grok": _sync_ai_activity,
        "github_copilot": _sync_dev_activity,
        "aider": _sync_dev_activity,
        "terminal": _sync_terminal_activity,
        "vscode": _sync_dev_activity,
        "ide": _sync_dev_activity,
    }
    return syncers[source](integration, user_id=user_id)


def sync_due_integrations(user_id: str = "local_user") -> dict:
    results = []
    now = _timestamp_ms()
    for integration in list_pcl_integrations(user_id):
        if integration.get("status") != "connected":
            continue
        next_sync_after = int(integration.get("next_sync_after") or 0)
        if next_sync_after and next_sync_after > now:
            results.append({
                "status": "skipped",
                "source": integration["source"],
                "reason": "next_sync_after_not_reached",
                "next_sync_after": next_sync_after,
            })
            continue
        results.append(sync_integration(integration["source"], user_id=user_id))
    return {
        "attempted": len(results),
        "synced": sum(1 for result in results if result.get("status") == "ok"),
        "skipped": sum(1 for result in results if result.get("status") == "skipped"),
        "results": results,
    }


def _sync_due(integration: dict) -> bool:
    next_sync_after = int(integration.get("next_sync_after") or 0)
    return not next_sync_after or next_sync_after <= _timestamp_ms()


def _refresh_expired_oauth_if_needed(integration: dict, user_id: str) -> dict:
    auth_status = str(integration.get("auth_status", ""))
    expires_at = int(integration.get("auth_expires_at") or 0)
    if not auth_status.startswith("oauth") or not expires_at:
        return {"status": "skipped"}
    if expires_at > _timestamp_ms() + 60_000:
        return {"status": "fresh"}
    result = refresh_oauth_token(integration["source"], user_id=user_id)
    if result.get("status") != "refreshed":
        update_pcl_integration_sync(
            source=integration["source"],
            status="error",
            items_synced=0,
            error=f"OAuth refresh required before sync: {result.get('error', 'refresh_failed')}",
            user_id=user_id,
        )
    return result


def sync_connected_integrations(user_id: str = "local_user") -> dict:
    results = []
    for integration in list_pcl_integrations(user_id):
        if integration.get("status") != "connected":
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


def _incremental_items(
    integration: dict,
    items: list[dict],
    timestamp_keys: tuple[str, ...],
) -> tuple[list[tuple[dict, int]], dict]:
    cursor = integration.get("sync_cursor") or {}
    last_seen = int(cursor.get("last_timestamp_ms", 0) or 0)
    selected: list[tuple[dict, int]] = []
    max_seen = last_seen
    for item in items:
        ts = _timestamp_ms(next((item.get(key) for key in timestamp_keys if item.get(key)), None))
        if ts <= last_seen:
            continue
        selected.append((item, ts))
        max_seen = max(max_seen, ts)
    next_cursor = {
        **cursor,
        "last_timestamp_ms": max_seen,
        "last_item_count": len(selected),
    }
    return selected, next_cursor


def _finish_sync(
    source: str,
    count: int,
    status: str = "ok",
    error: str = "",
    sync_cursor: dict | None = None,
    next_sync_after: int | None = None,
    user_id: str = "local_user",
) -> dict:
    if status == "ok":
        sync_cursor = {**(sync_cursor or {}), "retry_count": 0}
    updated = update_pcl_integration_sync(
        source=source,
        status=status,
        items_synced=count,
        error=error,
        sync_cursor=sync_cursor,
        next_sync_after=next_sync_after,
        user_id=user_id,
    )
    return {"status": status, "items_synced": count, "integration": updated}


def _missing_payload(source: str, expected: str, user_id: str = "local_user") -> dict:
    updated = _schedule_sync_retry(source, f"Import metadata required: {expected}", user_id=user_id)
    return {
        "status": "error",
        "error": "import_metadata_required",
        "expected": expected,
        "integration": updated,
    }


def _schedule_sync_retry(source: str, error: str, base_delay_seconds: int = 300, user_id: str = "local_user") -> dict:
    integration = get_pcl_integration(source, user_id=user_id) or {}
    cursor = integration.get("sync_cursor") or {}
    retry_count = min(int(cursor.get("retry_count", 0) or 0) + 1, 8)
    delay = min(base_delay_seconds * (2 ** (retry_count - 1)), 24 * 60 * 60)
    next_sync_after = _timestamp_ms() + (delay * 1000)
    return update_pcl_integration_sync(
        source=source,
        status="error",
        items_synced=0,
        error=error,
        sync_cursor={**cursor, "retry_count": retry_count, "last_error": error[:200]},
        next_sync_after=next_sync_after,
        user_id=user_id,
    )


def _sync_gmail(integration: dict, user_id: str = "local_user") -> dict:
    metadata = integration.get("metadata", {})
    messages = _metadata_items(metadata, "messages", "emails", "threads", "import_items")
    if not messages:
        live = _sync_gmail_live(integration, user_id=user_id)
        if live is not None:
            return live
    if not messages:
        return _missing_payload("gmail", "metadata.messages[]", user_id=user_id)

    selected, cursor = _incremental_items(integration, messages, ("timestamp", "date"))
    saved = 0
    for message, ts in selected:
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
        _remember_gmail_message(user_id, message, labels, sender_domain)
        if content["thread_size"] >= 3:
            _emit_connector_event(
                user_id=user_id,
                app_id="gmail",
                feature_id="multi-message-thread",
                timestamp=ts,
                subject_category="email",
            )
        saved += 1

    return _finish_sync("gmail", saved, sync_cursor=cursor, user_id=user_id)


def _sync_gmail_live(integration: dict, user_id: str = "local_user") -> dict | None:
    token = _get_access_token("gmail", user_id)
    if not token:
        return None

    from pcl.api_clients.google import fetch_gmail_messages

    cursor = integration.get("sync_cursor") or {}
    page_token = cursor.get("gmail_page_token")
    try:
        result = fetch_gmail_messages(token, max_results=50, page_token=page_token)
    except Exception as exc:
        return _sync_error("gmail", exc, user_id=user_id)

    saved = 0
    for message in result.get("messages", []):
        ts = _timestamp_ms(message.get("timestamp"))
        labels = [
            str(label).strip().lower()
            for label in message.get("labels", [])
            if str(label).strip()
        ]
        sender_domain = str(message.get("sender_domain", ""))[:120].lower()
        content = {
            "kind": "email_metadata",
            "labels": labels[:8],
            "sender_domain": sender_domain,
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
            label_clean = label.replace("category_", "").replace("_", " ")
            if label_clean in {"inbox", "unread", "sent", "spam", "trash"}:
                continue
            insert_persona_signal(
                source="gmail",
                signal_type="communication_label",
                name=f"email_label:{label_clean}",
                weight=1.0,
                confidence=0.65,
                evidence="Live Gmail label metadata",
                timestamp=ts,
            )
            _emit_connector_event(
                user_id=user_id,
                app_id="gmail",
                feature_id=f"label-{_feature_token(label_clean)}",
                timestamp=ts,
                subject_category="email",
            )
        if content["has_attachments"]:
            _emit_connector_event(
                user_id=user_id,
                app_id="gmail",
                feature_id="attachment-heavy-email",
                timestamp=ts,
                subject_category="email",
            )
        _remember_gmail_message(user_id, message, labels, sender_domain)
        saved += 1

    next_cursor = {
        **cursor,
        "gmail_page_token": result.get("next_page_token"),
        "last_item_count": saved,
        "live_api": True,
    }
    return _finish_sync(
        "gmail",
        saved,
        sync_cursor=next_cursor,
        next_sync_after=_timestamp_ms() + (6 * 60 * 60 * 1000),
        user_id=user_id,
    )


def _sync_calendar(integration: dict, user_id: str = "local_user") -> dict:
    metadata = integration.get("metadata", {})
    events = _metadata_items(metadata, "events", "meetings", "import_items")
    if not events:
        live = _sync_calendar_live(integration, user_id=user_id)
        if live is not None:
            return live
    if not events:
        return _missing_payload("calendar", "metadata.events[]", user_id=user_id)

    selected, cursor = _incremental_items(integration, events, ("start", "timestamp"))
    saved = 0
    for event, ts in selected:
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
        _remember_calendar_event(user_id, event, duration, attendees)
        saved += 1

    return _finish_sync("calendar", saved, sync_cursor=cursor, user_id=user_id)


def _sync_calendar_live(integration: dict, user_id: str = "local_user") -> dict | None:
    token = _get_access_token("calendar", user_id)
    if not token:
        return None

    from datetime import datetime, timezone

    from pcl.api_clients.google import fetch_calendar_events

    cursor = integration.get("sync_cursor") or {}
    sync_token = cursor.get("calendar_sync_token")
    time_min = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    try:
        result = fetch_calendar_events(token, sync_token=sync_token, time_min=None if sync_token else time_min)
    except Exception as exc:
        return _sync_error("calendar", exc, user_id=user_id)

    saved = 0
    for event in result.get("events", []):
        ts = _timestamp_ms(event.get("start"))
        attendees = max(0, int(event.get("attendee_count", 0) or 0))
        content = {
            "kind": "calendar_event_metadata",
            "attendee_count": attendees,
            "is_organizer": bool(event.get("is_organizer", False)),
            "status": str(event.get("status", "confirmed"))[:80],
            "hour_bucket": _hour_bucket(ts),
        }
        insert_feed_item(
            source="calendar",
            content_type="event_metadata",
            content=str(scrub_pii(content)),
            author="calendar",
            url="",
            timestamp=ts,
        )
        meeting_type = "solo" if attendees <= 1 else ("small_group" if attendees <= 4 else "large_group")
        insert_persona_signal(
            source="calendar",
            signal_type="meeting_pattern",
            name=f"meeting_type:{meeting_type}",
            weight=1.0,
            confidence=0.7,
            evidence="Live Calendar event metadata",
            timestamp=ts,
        )
        _emit_connector_event(
            user_id=user_id,
            app_id="calendar",
            feature_id=f"meeting-{meeting_type}",
            timestamp=ts,
            subject_category="meeting",
        )
        _remember_calendar_event(user_id, event, 0, attendees)
        saved += 1

    next_cursor = {
        **cursor,
        "calendar_sync_token": result.get("next_sync_token") or sync_token,
        "calendar_page_token": result.get("next_page_token"),
        "last_item_count": saved,
        "live_api": True,
    }
    return _finish_sync(
        "calendar",
        saved,
        sync_cursor=next_cursor,
        next_sync_after=_timestamp_ms() + (4 * 60 * 60 * 1000),
        user_id=user_id,
    )


def _sync_notion(integration: dict, user_id: str = "local_user") -> dict:
    metadata = integration.get("metadata", {})
    pages = _metadata_items(metadata, "pages", "page_activity", "import_items")
    if not pages:
        live = _sync_notion_live(integration, user_id=user_id)
        if live is not None:
            return live
    if not pages:
        return _missing_payload("notion", "metadata.pages[]", user_id=user_id)

    selected, cursor = _incremental_items(integration, pages, ("last_edited_time", "timestamp"))
    saved = 0
    for page, ts in selected:
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
        _remember_note_or_file(
            user_id=user_id,
            source="notion",
            title=str(page.get("title", page.get("name", object_type))).strip(),
            container=workspace,
            tags=tags,
            doc_type=object_type,
        )
        saved += 1

    return _finish_sync("notion", saved, sync_cursor=cursor, user_id=user_id)


def _sync_notion_live(integration: dict, user_id: str = "local_user") -> dict | None:
    token = _get_access_token("notion", user_id)
    if not token:
        return None

    from pcl.api_clients.notion import fetch_notion_pages

    cursor = integration.get("sync_cursor") or {}
    try:
        result = fetch_notion_pages(token, start_cursor=cursor.get("notion_cursor"))
    except Exception as exc:
        return _sync_error("notion", exc, user_id=user_id)

    saved = 0
    for page in result.get("pages", []):
        ts = _timestamp_ms(page.get("last_edited_time") or page.get("created_time"))
        object_type = _feature_token(page.get("object_type", "page"))
        parent_type = _feature_token(page.get("parent_type", "workspace"))
        content = {
            "kind": "notion_page_activity",
            "object_type": object_type,
            "parent_type": parent_type,
            "has_content": bool(page.get("has_content")),
            "hour_bucket": _hour_bucket(ts),
        }
        insert_feed_item(
            source="notion",
            content_type="page_activity",
            content=str(scrub_pii(content)),
            author=parent_type,
            url="",
            timestamp=ts,
        )
        insert_persona_signal(
            source="notion",
            signal_type="knowledge_work_tool",
            name=f"notion_{object_type}",
            weight=1.0,
            confidence=0.65,
            evidence="Live Notion page metadata",
            timestamp=ts,
        )
        _emit_connector_event(
            user_id=user_id,
            app_id="notion",
            feature_id=f"{object_type}-activity",
            timestamp=ts,
            subject_category="knowledge-work",
        )
        _remember_note_or_file(user_id, "notion", object_type, parent_type, [parent_type], object_type)
        saved += 1

    next_cursor = {
        **cursor,
        "notion_cursor": result.get("next_cursor"),
        "notion_has_more": result.get("has_more", False),
        "last_item_count": saved,
        "live_api": True,
    }
    return _finish_sync(
        "notion",
        saved,
        sync_cursor=next_cursor,
        next_sync_after=_timestamp_ms() + (6 * 60 * 60 * 1000),
        user_id=user_id,
    )


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
            user_id=user_id,
        )
        return {"status": "error", "error": "username_required", "integration": updated}

    if isinstance(metadata.get("repos"), list):
        try:
            from collectors.github import collect_github
            count = collect_github(username)
        except Exception as exc:
            updated = update_pcl_integration_sync(
                source="github",
                status="error",
                items_synced=0,
                error=str(exc),
                user_id=user_id,
            )
            return {"status": "error", "error": str(exc), "integration": updated}
        _remember_github_metadata(user_id, metadata)
        updated = update_pcl_integration_sync(
            source="github",
            status="ok",
            items_synced=count,
            error="",
            user_id=user_id,
        )
        return {"status": "ok", "items_synced": count, "integration": updated}

    try:
        from pcl.api_clients.github import fetch_starred_repos, fetch_user_events

        token = _get_access_token("github", user_id)
        events = fetch_user_events(username, access_token=token).get("events", [])
        stars = fetch_starred_repos(username, access_token=token).get("repos", [])
    except Exception as exc:
        updated = update_pcl_integration_sync(
            source="github",
            status="error",
            items_synced=0,
            error=str(exc),
            user_id=user_id,
        )
        return {"status": "error", "error": str(exc), "integration": updated}

    count = 0
    for event in events:
        ts = _timestamp_ms(event.get("created_at"))
        event_type = _feature_token(event.get("type", "event"))
        repo = str(event.get("repo", ""))[:160]
        content = {
            "kind": "github_event",
            "event_type": event_type,
            "repo": repo,
            "public": bool(event.get("public", True)),
            "hour_bucket": _hour_bucket(ts),
        }
        insert_feed_item("github", "public_event", str(scrub_pii(content)), repo, "", ts)
        insert_persona_signal(
            source="github",
            signal_type="developer_activity",
            name=f"github_event:{event_type}",
            weight=1.0,
            confidence=0.6,
            evidence="Live GitHub public event metadata",
            timestamp=ts,
        )
        _emit_connector_event(user_id, "github", f"event-{event_type}", ts, "development")
        count += 1
    for repo in stars:
        ts = _timestamp_ms(repo.get("starred_at"))
        language = _feature_token(repo.get("language", "unknown"))
        if language and language != "unknown":
            _emit_connector_event(user_id, "github", f"starred-language-{language}", ts, "development")
        for topic in repo.get("topics", [])[:5]:
            _emit_connector_event(user_id, "github", f"topic-{_feature_token(topic)}", ts, "development")
        count += 1

    _remember_github_metadata(user_id, metadata)

    updated = update_pcl_integration_sync(
        source="github",
        status="ok",
        items_synced=count,
        error="",
        sync_cursor={"live_api": True, "last_item_count": count},
        next_sync_after=_timestamp_ms() + (6 * 60 * 60 * 1000),
        user_id=user_id,
    )
    return {"status": "ok", "items_synced": count, "integration": updated}


def _sync_spotify(integration: dict, user_id: str = "local_user") -> dict:
    metadata = integration.get("metadata", {})
    plays = _metadata_items(metadata, "recently_played", "plays", "sessions", "import_items")
    if not plays:
        live = _sync_spotify_live(integration, user_id=user_id)
        if live is not None:
            return live
    if not plays:
        return _missing_payload("spotify", "metadata.recently_played[]", user_id=user_id)

    selected, cursor = _incremental_items(integration, plays, ("played_at", "timestamp"))
    saved = 0
    for play, ts in selected:
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

    return _finish_sync("spotify", saved, sync_cursor=cursor, user_id=user_id)


def _sync_spotify_live(integration: dict, user_id: str = "local_user") -> dict | None:
    token = _get_access_token("spotify", user_id)
    if not token:
        return None

    from pcl.api_clients.spotify import fetch_recently_played, fetch_top_genres

    cursor = integration.get("sync_cursor") or {}
    try:
        recent = fetch_recently_played(token, after_ms=cursor.get("spotify_after"))
        genres = fetch_top_genres(token).get("genre_counts", {})
    except Exception as exc:
        return _sync_error("spotify", exc, user_id=user_id)

    saved = 0
    for play in recent.get("tracks", []):
        ts = _timestamp_ms(play.get("played_at"))
        duration = int(play.get("duration_ms", 0) or 0) // 60000
        content = {
            "kind": "spotify_session_metadata",
            "duration_minutes": duration,
            "artist_count": int(play.get("artist_count", 0) or 0),
            "popularity_bucket": _popularity_bucket(play.get("popularity", 0)),
            "explicit": bool(play.get("explicit", False)),
            "hour_bucket": _hour_bucket(ts),
        }
        insert_feed_item("spotify", "session_metadata", str(scrub_pii(content)), "spotify", "", ts)
        if duration >= 20:
            insert_persona_signal(
                source="spotify",
                signal_type="focus_pattern",
                name="long_focus_audio_session",
                weight=min(duration / 45, 3.0),
                confidence=0.55,
                evidence="Live Spotify listening metadata",
                timestamp=ts,
            )
            _emit_connector_event(user_id, "spotify", "long-focus-session", ts, "focus")
        saved += 1
    for genre, count in sorted(genres.items(), key=lambda item: item[1], reverse=True)[:8]:
        _emit_connector_event(user_id, "spotify", f"genre-{_feature_token(genre)}", _timestamp_ms(), "focus")
        if count:
            saved += 1

    next_cursor = {
        **cursor,
        "spotify_after": recent.get("next_after") or cursor.get("spotify_after"),
        "last_item_count": saved,
        "live_api": True,
    }
    return _finish_sync(
        "spotify",
        saved,
        sync_cursor=next_cursor,
        next_sync_after=_timestamp_ms() + (6 * 60 * 60 * 1000),
        user_id=user_id,
    )


def _sync_youtube(integration: dict, user_id: str = "local_user") -> dict:
    metadata = integration.get("metadata", {})
    videos = _metadata_items(metadata, "watch_history", "videos", "sessions", "import_items")
    if not videos:
        live = _sync_youtube_live(integration, user_id=user_id)
        if live is not None:
            return live
    if not videos:
        return _missing_payload("youtube", "metadata.watch_history[]", user_id=user_id)

    selected, cursor = _incremental_items(integration, videos, ("watched_at", "timestamp"))
    saved = 0
    for video, ts in selected:
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

    return _finish_sync("youtube", saved, sync_cursor=cursor, user_id=user_id)


def _sync_youtube_live(integration: dict, user_id: str = "local_user") -> dict | None:
    token = _get_access_token("youtube", user_id)
    if not token:
        return None

    from pcl.api_clients.google import fetch_youtube_activity

    try:
        result = fetch_youtube_activity(token)
    except Exception as exc:
        return _sync_error("youtube", exc, user_id=user_id)

    saved = 0
    for video in result.get("videos", []):
        ts = _timestamp_ms(video.get("watched_at"))
        category = _feature_token(video.get("category", "video"))
        content = {
            "kind": "youtube_activity_metadata",
            "category": category,
            "duration_minutes": int(video.get("duration_minutes", 0) or 0),
            "hour_bucket": _hour_bucket(ts),
        }
        insert_feed_item("youtube", "watch_metadata", str(scrub_pii(content)), "youtube", "", ts)
        insert_persona_signal(
            source="youtube",
            signal_type="learning_pattern",
            name=f"youtube_category:{category}",
            weight=1.0,
            confidence=0.5,
            evidence="Live YouTube account activity metadata",
            timestamp=ts,
        )
        _emit_connector_event(user_id, "youtube", f"category-{category}", ts, "learning")
        saved += 1

    return _finish_sync(
        "youtube",
        saved,
        sync_cursor={**(integration.get("sync_cursor") or {}), "last_item_count": saved, "live_api": True},
        next_sync_after=_timestamp_ms() + (12 * 60 * 60 * 1000),
        user_id=user_id,
    )


def _sync_apple_health(integration: dict, user_id: str = "local_user") -> dict:
    metadata = integration.get("metadata", {})
    samples = _metadata_items(metadata, "activity", "daily_activity", "samples", "import_items")
    if not samples:
        return _missing_payload("apple_health", "metadata.activity[]", user_id=user_id)

    selected, cursor = _incremental_items(integration, samples, ("date", "timestamp"))
    saved = 0
    for sample, ts in selected:
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

    return _finish_sync("apple_health", saved, sync_cursor=cursor, user_id=user_id)


def _sync_google_drive(integration: dict, user_id: str = "local_user") -> dict:
    metadata = integration.get("metadata", {})
    files = _metadata_items(metadata, "files", "documents", "file_activity", "import_items")
    if not files:
        live = _sync_google_drive_live(integration, user_id=user_id)
        if live is not None:
            return live
    if not files:
        return _missing_payload("google_drive", "metadata.files[]", user_id=user_id)

    selected, cursor = _incremental_items(integration, files, ("last_edited_time", "modified_time", "timestamp"))
    saved = 0
    for file_item, ts in selected:
        mime_type = str(file_item.get("mime_type", file_item.get("type", "file")))[:120]
        folder = str(file_item.get("folder", file_item.get("folder_name", "")))[:120]
        owner_domain = str(file_item.get("owner_domain", ""))[:120].lower()
        doc_type = _drive_doc_type(mime_type)
        content = {
            "kind": "google_drive_file_metadata",
            "doc_type": doc_type,
            "folder": folder,
            "owner_domain": owner_domain,
            "hour_bucket": _hour_bucket(ts),
        }
        insert_feed_item(
            source="google_drive",
            content_type="file_metadata",
            content=str(scrub_pii(content)),
            author=owner_domain,
            url="",
            timestamp=ts,
        )
        insert_persona_signal(
            source="google_drive",
            signal_type="document_work",
            name=f"drive_doc_type:{doc_type}",
            weight=1.0,
            confidence=0.6,
            evidence="Imported Google Drive metadata",
            timestamp=ts,
        )
        _emit_connector_event(
            user_id=user_id,
            app_id="google-drive",
            feature_id=f"{doc_type}-activity",
            timestamp=ts,
            subject_category="document-work",
        )
        if folder:
            _emit_connector_event(
                user_id=user_id,
                app_id="google-drive",
                feature_id=f"folder-{_feature_token(folder)}",
                timestamp=ts,
                subject_category="document-work",
            )
        _remember_note_or_file(
            user_id=user_id,
            source="google_drive",
            title=str(file_item.get("name", file_item.get("title", doc_type))).strip(),
            container=folder,
            tags=[doc_type],
            doc_type=doc_type,
        )
        saved += 1

    return _finish_sync("google_drive", saved, sync_cursor=cursor, user_id=user_id)


def _sync_google_drive_live(integration: dict, user_id: str = "local_user") -> dict | None:
    token = _get_access_token("google_drive", user_id)
    if not token:
        return None

    from pcl.api_clients.google import fetch_drive_activity

    try:
        result = fetch_drive_activity(token)
    except Exception as exc:
        return _sync_error("google_drive", exc, user_id=user_id)

    saved = 0
    for file_item in result.get("files", []):
        ts = _timestamp_ms(file_item.get("modified_at") or file_item.get("viewed_at"))
        mime_type = str(file_item.get("mime_type", "file"))[:120]
        doc_type = _drive_doc_type(mime_type)
        content = {
            "kind": "google_drive_file_metadata",
            "doc_type": doc_type,
            "file_category": file_item.get("file_category", doc_type),
            "is_shared": bool(file_item.get("is_shared", False)),
            "hour_bucket": _hour_bucket(ts),
        }
        insert_feed_item("google_drive", "file_metadata", str(scrub_pii(content)), "google_drive", "", ts)
        insert_persona_signal(
            source="google_drive",
            signal_type="document_work",
            name=f"drive_doc_type:{doc_type}",
            weight=1.0,
            confidence=0.6,
            evidence="Live Google Drive metadata",
            timestamp=ts,
        )
        _emit_connector_event(user_id, "google-drive", f"{doc_type}-activity", ts, "document-work")
        if content["is_shared"]:
            _emit_connector_event(user_id, "google-drive", "shared-file-activity", ts, "document-work")
        _remember_note_or_file(user_id, "google_drive", doc_type, "", [doc_type], doc_type)
        saved += 1

    return _finish_sync(
        "google_drive",
        saved,
        sync_cursor={**(integration.get("sync_cursor") or {}), "last_item_count": saved, "live_api": True},
        next_sync_after=_timestamp_ms() + (6 * 60 * 60 * 1000),
        user_id=user_id,
    )


def _sync_slack(integration: dict, user_id: str = "local_user") -> dict:
    token = _get_access_token("slack", user_id)
    if not token:
        return _missing_payload("slack", "oauth token", user_id=user_id)

    from pcl.api_clients.slack import fetch_channel_activity

    try:
        result = fetch_channel_activity(token)
    except Exception as exc:
        return _sync_error("slack", exc, user_id=user_id)

    saved = 0
    for activity in result.get("channel_activity", []):
        ts = _timestamp_ms()
        channel_type = "private" if activity.get("is_private") else "public"
        user_messages = int(activity.get("user_message_count", 0) or 0)
        content = {
            "kind": "slack_channel_activity",
            "channel_type": channel_type,
            "recent_message_count": int(activity.get("recent_message_count", 0) or 0),
            "user_message_count": user_messages,
            "hour_bucket": _hour_bucket(ts),
        }
        insert_feed_item("slack", "channel_activity", str(scrub_pii(content)), "slack", "", ts)
        insert_persona_signal(
            source="slack",
            signal_type="communication_pattern",
            name=f"slack:{channel_type}_channel_active",
            weight=min(user_messages / 10.0, 1.0),
            confidence=0.7,
            evidence="Live Slack channel activity metadata",
            timestamp=ts,
        )
        _emit_connector_event(user_id, "slack", f"{channel_type}-channel-active", ts, "communication")
        saved += 1

    return _finish_sync(
        "slack",
        saved,
        sync_cursor={"live_api": True, "last_item_count": saved, "channel_count": result.get("channel_count", 0)},
        next_sync_after=_timestamp_ms() + (3 * 60 * 60 * 1000),
        user_id=user_id,
    )


def _sync_linear(integration: dict, user_id: str = "local_user") -> dict:
    token = _get_access_token("linear", user_id)
    if not token:
        return _missing_payload("linear", "oauth token", user_id=user_id)

    from pcl.api_clients.linear import fetch_assigned_issues

    try:
        result = fetch_assigned_issues(token)
    except Exception as exc:
        return _sync_error("linear", exc, user_id=user_id)

    issues = result.get("issues", [])
    saved = _sync_task_issue_signals("linear", issues, user_id=user_id)
    return _finish_sync(
        "linear",
        saved,
        sync_cursor={"live_api": True, "last_item_count": saved},
        next_sync_after=_timestamp_ms() + (2 * 60 * 60 * 1000),
        user_id=user_id,
    )


def _sync_todoist(integration: dict, user_id: str = "local_user") -> dict:
    token = _get_access_token("todoist", user_id)
    if not token:
        return _missing_payload("todoist", "oauth token", user_id=user_id)

    from pcl.api_clients.tasks import fetch_todoist_tasks

    try:
        result = fetch_todoist_tasks(token)
    except Exception as exc:
        return _sync_error("todoist", exc, user_id=user_id)

    tasks = result.get("tasks", [])
    saved = 0
    for task in tasks:
        ts = _timestamp_ms(task.get("created_at"))
        priority = _feature_token(task.get("priority", "normal"))
        content = {
            "kind": "todoist_task_metadata",
            "priority": priority,
            "has_project": bool(task.get("project_id")),
            "due_recurring": bool(task.get("due_recurring", False)),
            "hour_bucket": _hour_bucket(ts),
        }
        insert_feed_item("todoist", "task_metadata", str(scrub_pii(content)), "todoist", "", ts)
        _emit_connector_event(user_id, "todoist", f"priority-{priority}", ts, "task-management")
        if content["due_recurring"]:
            insert_persona_signal("todoist", "task_pattern", "recurring_tasks", 0.8, 0.65, "Live Todoist task metadata", ts)
        saved += 1

    return _finish_sync(
        "todoist",
        saved,
        sync_cursor={"live_api": True, "last_item_count": saved},
        next_sync_after=_timestamp_ms() + (3 * 60 * 60 * 1000),
        user_id=user_id,
    )


def _sync_strava(integration: dict, user_id: str = "local_user") -> dict:
    token = _get_access_token("strava", user_id)
    if not token:
        return _missing_payload("strava", "oauth token", user_id=user_id)

    from pcl.api_clients.fitness import fetch_strava_activities

    cursor = integration.get("sync_cursor") or {}
    try:
        result = fetch_strava_activities(token, after=cursor.get("strava_after"))
    except Exception as exc:
        return _sync_error("strava", exc, user_id=user_id)

    saved = 0
    latest = int(cursor.get("strava_after", 0) or 0)
    for activity in result.get("activities", []):
        ts = _timestamp_ms(activity.get("start_date"))
        latest = max(latest, ts // 1000)
        activity_type = _feature_token(activity.get("type", "activity"))
        moving_minutes = int(activity.get("moving_time", 0) or 0) // 60
        content = {
            "kind": "strava_activity_metadata",
            "activity_type": activity_type,
            "moving_minutes": moving_minutes,
            "distance_bucket": _distance_bucket(activity.get("distance", 0)),
            "hour_bucket": _hour_bucket(ts),
        }
        insert_feed_item("strava", "activity_metadata", str(scrub_pii(content)), "strava", "", ts)
        insert_persona_signal(
            source="strava",
            signal_type="fitness_pattern",
            name=f"activity_type:{activity_type}",
            weight=min(max(moving_minutes, 1) / 45, 3.0),
            confidence=0.65,
            evidence="Live Strava activity metadata",
            timestamp=ts,
        )
        _emit_connector_event(user_id, "strava", f"activity-{activity_type}", ts, "fitness")
        saved += 1

    return _finish_sync(
        "strava",
        saved,
        sync_cursor={"live_api": True, "last_item_count": saved, "strava_after": latest},
        next_sync_after=_timestamp_ms() + (6 * 60 * 60 * 1000),
        user_id=user_id,
    )


def _sync_jira(integration: dict, user_id: str = "local_user") -> dict:
    token = _get_access_token("jira", user_id)
    cloud_id = str((integration.get("metadata") or {}).get("cloud_id", "")).strip()
    if not token:
        return _missing_payload("jira", "oauth token", user_id=user_id)
    if not cloud_id:
        return _missing_payload("jira", "metadata.cloud_id", user_id=user_id)
    from pcl.api_clients.tasks import fetch_jira_issues
    try:
        result = fetch_jira_issues(token, cloud_id)
    except Exception as exc:
        return _sync_error("jira", exc, user_id=user_id)
    saved = _sync_task_issue_signals("jira", result.get("issues", []), user_id=user_id)
    return _finish_sync("jira", saved, sync_cursor={"live_api": True, "last_item_count": saved}, next_sync_after=_timestamp_ms() + (3 * 60 * 60 * 1000), user_id=user_id)


def _sync_reddit(integration: dict, user_id: str = "local_user") -> dict:
    token = _get_access_token("reddit", user_id)
    if not token:
        return _missing_payload("reddit", "oauth token", user_id=user_id)
    from pcl.api_clients.reddit import fetch_reddit_activity
    try:
        result = fetch_reddit_activity(token)
    except Exception as exc:
        return _sync_error("reddit", exc, user_id=user_id)
    saved = 0
    for item in result.get("items", []):
        ts = _timestamp_ms(item.get("created_utc"))
        subreddit = _feature_token(item.get("subreddit", "community"))
        content = {"kind": "reddit_activity", "subreddit": subreddit, "score_bucket": item.get("score_bucket", "low"), "hour_bucket": _hour_bucket(ts)}
        insert_feed_item("reddit", "activity_metadata", str(scrub_pii(content)), subreddit, "", ts)
        insert_persona_signal("reddit", "community_interest", f"reddit:{subreddit}", 1.0, 0.5, "Live Reddit activity metadata", ts)
        _emit_connector_event(user_id, "reddit", f"community-{subreddit}", ts, "social")
        saved += 1
    return _finish_sync("reddit", saved, sync_cursor={"live_api": True, "last_item_count": saved}, next_sync_after=_timestamp_ms() + (6 * 60 * 60 * 1000), user_id=user_id)


def _sync_figma(integration: dict, user_id: str = "local_user") -> dict:
    token = _get_access_token("figma", user_id)
    if not token:
        return _missing_payload("figma", "oauth token", user_id=user_id)
    from pcl.api_clients.storage import fetch_figma_files
    try:
        result = fetch_figma_files(token)
    except Exception as exc:
        return _sync_error("figma", exc, user_id=user_id)
    ts = _timestamp_ms()
    profile = result.get("profile", {})
    insert_feed_item("figma", "design_tool_metadata", str(scrub_pii({"kind": "figma_profile", "team_count": profile.get("team_count", 0)})), "figma", "", ts)
    insert_persona_signal("figma", "design_tool", "figma_active", 1.0, 0.5, "Live Figma account metadata", ts)
    _emit_connector_event(user_id, "figma", "design-tool-active", ts, "design")
    return _finish_sync("figma", 1, sync_cursor={"live_api": True, "last_item_count": 1}, next_sync_after=_timestamp_ms() + (12 * 60 * 60 * 1000), user_id=user_id)


def _sync_dropbox(integration: dict, user_id: str = "local_user") -> dict:
    token = _get_access_token("dropbox", user_id)
    if not token:
        return _missing_payload("dropbox", "oauth token", user_id=user_id)
    from pcl.api_clients.storage import fetch_dropbox_activity
    try:
        result = fetch_dropbox_activity(token)
    except Exception as exc:
        return _sync_error("dropbox", exc, user_id=user_id)
    saved = _sync_storage_file_signals("dropbox", result.get("files", []), user_id=user_id)
    return _finish_sync("dropbox", saved, sync_cursor={"live_api": True, "last_item_count": saved}, next_sync_after=_timestamp_ms() + (6 * 60 * 60 * 1000), user_id=user_id)


def _sync_onedrive(integration: dict, user_id: str = "local_user") -> dict:
    token = _get_access_token("onedrive", user_id)
    if not token:
        return _missing_payload("onedrive", "oauth token", user_id=user_id)
    from pcl.api_clients.storage import fetch_onedrive_activity
    try:
        result = fetch_onedrive_activity(token)
    except Exception as exc:
        return _sync_error("onedrive", exc, user_id=user_id)
    saved = _sync_storage_file_signals("onedrive", result.get("files", []), user_id=user_id)
    return _finish_sync("onedrive", saved, sync_cursor={"live_api": True, "last_item_count": saved}, next_sync_after=_timestamp_ms() + (6 * 60 * 60 * 1000), user_id=user_id)


def _sync_trello(integration: dict, user_id: str = "local_user") -> dict:
    token = _get_access_token("trello", user_id)
    api_key = str((integration.get("metadata") or {}).get("api_key", "")).strip()
    if not token:
        return _missing_payload("trello", "oauth token", user_id=user_id)
    from pcl.api_clients.tasks import fetch_trello_cards
    try:
        result = fetch_trello_cards(token, api_key=api_key or None)
    except Exception as exc:
        return _sync_error("trello", exc, user_id=user_id)
    saved = _sync_task_issue_signals("trello", result.get("cards", []), user_id=user_id)
    return _finish_sync("trello", saved, sync_cursor={"live_api": True, "last_item_count": saved}, next_sync_after=_timestamp_ms() + (3 * 60 * 60 * 1000), user_id=user_id)


def _sync_asana(integration: dict, user_id: str = "local_user") -> dict:
    token = _get_access_token("asana", user_id)
    if not token:
        return _missing_payload("asana", "oauth token", user_id=user_id)
    from pcl.api_clients.tasks import fetch_asana_tasks
    try:
        result = fetch_asana_tasks(token)
    except Exception as exc:
        return _sync_error("asana", exc, user_id=user_id)
    saved = _sync_task_issue_signals("asana", result.get("tasks", []), user_id=user_id)
    return _finish_sync("asana", saved, sync_cursor={"live_api": True, "last_item_count": saved}, next_sync_after=_timestamp_ms() + (3 * 60 * 60 * 1000), user_id=user_id)


def _sync_social_activity(integration: dict, user_id: str = "local_user") -> dict:
    source = integration["source"]
    metadata = integration.get("metadata", {})
    items = _metadata_items(metadata, "items", "posts", "feed", "events", "import_items")
    if not items:
        return _missing_payload(source, "metadata.items[]", user_id=user_id)

    selected, cursor = _incremental_items(integration, items, ("timestamp", "created_at", "seen_at", "watched_at"))
    saved = 0
    for item, ts in selected:
        topic = _feature_token(item.get("topic", item.get("category", item.get("hashtag", "feed"))))
        content_type = _feature_token(item.get("content_type", item.get("type", "feed_activity")))
        author_role = str(item.get("author_role", item.get("creator_category", "")))[:120]
        engagement = _feature_token(item.get("engagement", item.get("action", "viewed")))
        content = {
            "kind": f"{source}_activity_metadata",
            "content_type": content_type,
            "topic": topic,
            "author_role": author_role,
            "engagement": engagement,
            "hour_bucket": _hour_bucket(ts),
        }
        insert_feed_item(
            source=source,
            content_type="feed_activity",
            content=str(scrub_pii(content)),
            author=author_role,
            url="",
            timestamp=ts,
        )
        insert_persona_signal(
            source=source,
            signal_type="social_topic",
            name=f"{source}_topic:{topic}",
            weight=1.0,
            confidence=0.5,
            evidence=f"Imported {source} activity metadata",
            timestamp=ts,
        )
        _emit_connector_event(
            user_id=user_id,
            app_id=source,
            feature_id=f"topic-{topic}",
            timestamp=ts,
            subject_category="social",
        )
        _emit_connector_event(
            user_id=user_id,
            app_id=source,
            feature_id=f"{content_type}-{engagement}",
            timestamp=ts,
            subject_category="social",
        )
        saved += 1

    return _finish_sync(source, saved, sync_cursor=cursor, user_id=user_id)


def _sync_ai_activity(integration: dict, user_id: str = "local_user") -> dict:
    source = integration["source"]
    metadata = integration.get("metadata", {})
    sessions = _metadata_items(metadata, "sessions", "queries", "prompts", "events", "import_items")
    if not sessions:
        return _missing_payload(source, "metadata.sessions[]", user_id=user_id)

    selected, cursor = _incremental_items(integration, sessions, ("timestamp", "created_at", "started_at"))
    saved = 0
    for session, ts in selected:
        task_type = _feature_token(session.get("task_type", session.get("topic", session.get("intent", "assistant"))))
        model = _feature_token(session.get("model", source))
        length_bucket = _feature_token(session.get("prompt_length_bucket", session.get("length_bucket", "unknown")))
        content = {
            "kind": f"{source}_assistant_session_metadata",
            "task_type": task_type,
            "model": model,
            "prompt_length_bucket": length_bucket,
            "hour_bucket": _hour_bucket(ts),
        }
        insert_feed_item(
            source=source,
            content_type="assistant_session_metadata",
            content=str(scrub_pii(content)),
            author=source,
            url="",
            timestamp=ts,
        )
        insert_persona_signal(
            source=source,
            signal_type="ai_workflow",
            name=f"{source}_task:{task_type}",
            weight=1.0,
            confidence=0.55,
            evidence=f"Imported {source} session metadata",
            timestamp=ts,
        )
        _emit_connector_event(
            user_id=user_id,
            app_id=source,
            feature_id=f"task-{task_type}",
            timestamp=ts,
            subject_category="ai-workflow",
        )
        if model and model != source:
            _emit_connector_event(
                user_id=user_id,
                app_id=source,
                feature_id=f"model-{model}",
                timestamp=ts,
                subject_category="ai-workflow",
            )
        saved += 1

    return _finish_sync(source, saved, sync_cursor=cursor, user_id=user_id)


def _sync_dev_activity(integration: dict, user_id: str = "local_user") -> dict:
    source = integration["source"]
    metadata = integration.get("metadata", {})
    sessions = _metadata_items(metadata, "sessions", "projects", "events", "import_items")
    if not sessions:
        return _missing_payload(source, "metadata.sessions[]", user_id=user_id)

    selected, cursor = _incremental_items(integration, sessions, ("timestamp", "started_at", "ended_at", "last_active_at"))
    saved = 0
    for session, ts in selected:
        project = _feature_token(session.get("project", session.get("repo", "project")))
        language = _feature_token(session.get("language", session.get("primary_language", "unknown")))
        task_type = _feature_token(session.get("task_type", session.get("assistant_action", "coding")))
        active_minutes = int(session.get("active_minutes", session.get("duration_minutes", 0)) or 0)
        content = {
            "kind": f"{source}_dev_session_metadata",
            "project": project,
            "language": language,
            "task_type": task_type,
            "active_minutes": active_minutes,
            "hour_bucket": _hour_bucket(ts),
        }
        insert_feed_item(
            source=source,
            content_type="dev_session_metadata",
            content=str(scrub_pii(content)),
            author=project,
            url="",
            timestamp=ts,
        )
        insert_persona_signal(
            source=source,
            signal_type="developer_workflow",
            name=f"{source}_task:{task_type}",
            weight=1.0,
            confidence=0.6,
            evidence=f"Imported {source} development metadata",
            timestamp=ts,
        )
        _emit_connector_event(
            user_id=user_id,
            app_id=source,
            feature_id=f"project-{project}",
            timestamp=ts,
            subject_category="development",
        )
        _emit_connector_event(
            user_id=user_id,
            app_id=source,
            feature_id=f"language-{language}",
            timestamp=ts,
            subject_category="development",
        )
        _emit_connector_event(
            user_id=user_id,
            app_id=source,
            feature_id=f"task-{task_type}",
            timestamp=ts,
            subject_category="development",
        )
        if active_minutes >= 30:
            _emit_connector_event(
                user_id=user_id,
                app_id=source,
                feature_id="deep-work-session",
                timestamp=ts,
                subject_category="development",
            )
        saved += 1

    return _finish_sync(source, saved, sync_cursor=cursor, user_id=user_id)


def _sync_terminal_activity(integration: dict, user_id: str = "local_user") -> dict:
    metadata = integration.get("metadata", {})
    commands = _metadata_items(metadata, "commands", "sessions", "events", "import_items")
    if not commands:
        return _missing_payload("terminal", "metadata.commands[]", user_id=user_id)

    selected, cursor = _incremental_items(integration, commands, ("timestamp", "started_at"))
    saved = 0
    for command, ts in selected:
        project = _feature_token(command.get("project", "terminal"))
        category = _feature_token(command.get("command_category", command.get("category", "command")))
        shell = _feature_token(command.get("shell", "shell"))
        content = {
            "kind": "terminal_command_metadata",
            "project": project,
            "command_category": category,
            "shell": shell,
            "hour_bucket": _hour_bucket(ts),
        }
        insert_feed_item(
            source="terminal",
            content_type="command_metadata",
            content=str(scrub_pii(content)),
            author=project,
            url="",
            timestamp=ts,
        )
        insert_persona_signal(
            source="terminal",
            signal_type="terminal_workflow",
            name=f"terminal_command:{category}",
            weight=1.0,
            confidence=0.55,
            evidence="Imported terminal command metadata",
            timestamp=ts,
        )
        _emit_connector_event(
            user_id=user_id,
            app_id="terminal",
            feature_id=f"command-{category}",
            timestamp=ts,
            subject_category="development",
        )
        _emit_connector_event(
            user_id=user_id,
            app_id="terminal",
            feature_id=f"project-{project}",
            timestamp=ts,
            subject_category="development",
        )
        saved += 1

    return _finish_sync("terminal", saved, sync_cursor=cursor, user_id=user_id)


def _get_access_token(source: str, user_id: str) -> str:
    from database import get_decrypted_pcl_integration_oauth_token

    token = get_decrypted_pcl_integration_oauth_token(source, user_id)
    if not token:
        return ""
    return str(token.get("access_token") or token.get("token") or "").strip()


def _sync_error(source: str, exc: Exception, user_id: str = "local_user") -> dict:
    updated = update_pcl_integration_sync(
        source=source,
        status="error",
        items_synced=0,
        error=str(exc),
        sync_cursor={**((get_pcl_integration(source, user_id=user_id) or {}).get("sync_cursor") or {}), "last_error": str(exc)[:200]},
        next_sync_after=_timestamp_ms() + (15 * 60 * 1000),
        user_id=user_id,
    )
    return {"status": "error", "error": str(exc), "integration": updated}


def _sync_task_issue_signals(source: str, items: list[dict], user_id: str = "local_user") -> int:
    saved = 0
    completed = 0
    for item in items:
        ts = _timestamp_ms(item.get("updated_at") or item.get("created_at") or item.get("completed_at"))
        status = _feature_token(item.get("state_type", item.get("status", "open")))
        priority = _feature_token(item.get("priority", "normal"))
        if status in {"completed", "done"} or item.get("completed") is True or item.get("due_complete") is True:
            completed += 1
        content = {
            "kind": f"{source}_task_metadata",
            "status": status,
            "priority": priority,
            "hour_bucket": _hour_bucket(ts),
        }
        insert_feed_item(source, "task_metadata", str(scrub_pii(content)), source, "", ts)
        _emit_connector_event(user_id, source, f"status-{status}", ts, "task-management")
        if priority and priority != "normal":
            _emit_connector_event(user_id, source, f"priority-{priority}", ts, "task-management")
        saved += 1
    if items:
        insert_persona_signal(
            source=source,
            signal_type="work_pattern",
            name=f"{source}:completion_rate",
            weight=completed / max(len(items), 1),
            confidence=0.7,
            evidence=f"Live {source} task metadata",
            timestamp=_timestamp_ms(),
        )
    return saved


def _sync_storage_file_signals(source: str, files: list[dict], user_id: str = "local_user") -> int:
    saved = 0
    for item in files:
        ts = _timestamp_ms(item.get("modified_at") or item.get("server_modified") or item.get("client_modified"))
        mime_type = str(item.get("mime_type") or item.get("tag") or "file")
        doc_type = _drive_doc_type(mime_type)
        content = {
            "kind": f"{source}_file_metadata",
            "doc_type": doc_type,
            "is_shared": bool(item.get("is_shared", False)),
            "hour_bucket": _hour_bucket(ts),
        }
        insert_feed_item(source, "file_metadata", str(scrub_pii(content)), source, "", ts)
        insert_persona_signal(source, "document_work", f"{source}_doc_type:{doc_type}", 1.0, 0.55, f"Live {source} file metadata", ts)
        _emit_connector_event(user_id, source, f"{doc_type}-activity", ts, "document-work")
        saved += 1
    return saved


def _popularity_bucket(value: Any) -> str:
    try:
        score = int(value or 0)
    except (TypeError, ValueError):
        score = 0
    if score >= 70:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


def _distance_bucket(value: Any) -> str:
    try:
        meters = float(value or 0)
    except (TypeError, ValueError):
        meters = 0
    if meters >= 20_000:
        return "long"
    if meters >= 5_000:
        return "medium"
    return "short"


def _remember_gmail_message(user_id: str, message: dict, labels: list[str], sender_domain: str) -> None:
    sender = str(message.get("sender", message.get("from", sender_domain))).strip()
    subject = str(message.get("subject", message.get("topic", ""))).strip()
    project = str(message.get("project", message.get("account", ""))).strip()
    people = [
        str(item).strip()
        for item in message.get("people", message.get("participants", []))
        if str(item).strip()
    ]
    if sender:
        _remember_source_fact(
            user_id,
            "gmail",
            "people",
            f"{sender} appears in Gmail conversations.",
            "Gmail sender metadata",
        )
    for person in people[:8]:
        _remember_source_fact(
            user_id,
            "gmail",
            "people",
            f"{person} appears in Gmail conversations.",
            "Gmail participant metadata",
        )
    if project:
        _remember_source_fact(
            user_id,
            "gmail",
            "projects",
            f"Gmail mentions active project: {project}.",
            "Gmail project metadata",
        )
    if subject:
        _remember_source_fact(
            user_id,
            "gmail",
            "daily-log",
            f"Gmail topic seen: {subject}.",
            "Gmail subject metadata",
        )
    for label in labels[:5]:
        _remember_source_fact(
            user_id,
            "gmail",
            "preferences",
            f"Gmail frequently uses label: {label}.",
            "Gmail label metadata",
        )


def _remember_calendar_event(user_id: str, event: dict, duration: int, attendees: int) -> None:
    title = str(event.get("title", event.get("summary", event.get("name", "")))).strip()
    project = str(event.get("project", event.get("calendar", ""))).strip()
    people = [
        str(item).strip()
        for item in event.get("people", event.get("attendees", []))
        if str(item).strip()
    ]
    if title:
        _remember_source_fact(
            user_id,
            "calendar",
            "daily-log",
            f"Calendar event observed: {title}.",
            "Calendar event title",
        )
    if project:
        _remember_source_fact(
            user_id,
            "calendar",
            "projects",
            f"Calendar activity relates to project: {project}.",
            "Calendar project metadata",
        )
    if duration:
        _remember_source_fact(
            user_id,
            "calendar",
            "preferences",
            f"Calendar routine includes {duration}-minute meetings.",
            "Calendar duration metadata",
        )
    if attendees >= 3:
        _remember_source_fact(
            user_id,
            "calendar",
            "work-style",
            "Calendar pattern: participates in group meetings.",
            "Calendar attendee metadata",
        )
    for person in people[:8]:
        _remember_source_fact(
            user_id,
            "calendar",
            "people",
            f"{person} appears in calendar meetings.",
            "Calendar attendee metadata",
        )


def _remember_github_metadata(user_id: str, metadata: dict) -> None:
    repos = _metadata_items(metadata, "repos", "repositories", "projects", "import_items")
    if not repos and metadata.get("username"):
        _remember_source_fact(
            user_id,
            "github",
            "profile",
            f"GitHub account connected: {metadata['username']}.",
            "GitHub account metadata",
        )
        return
    for repo in repos[:30]:
        name = str(repo.get("name", repo.get("repo", ""))).strip()
        language = str(repo.get("language", repo.get("primary_language", ""))).strip()
        stack = [
            str(item).strip()
            for item in repo.get("stack", repo.get("topics", []))
            if str(item).strip()
        ]
        active = bool(repo.get("active", repo.get("recent_activity", True)))
        if name:
            _remember_source_fact(
                user_id,
                "github",
                "projects",
                f"GitHub repo tracked: {name}{' (active)' if active else ''}.",
                "GitHub repository metadata",
            )
        if language:
            _remember_source_fact(
                user_id,
                "github",
                "work-style",
                f"Uses {language} in GitHub projects.",
                "GitHub language metadata",
            )
        for item in stack[:8]:
            _remember_source_fact(
                user_id,
                "github",
                "work-style",
                f"GitHub stack/topic includes {item}.",
                "GitHub topic metadata",
            )


def _remember_note_or_file(
    user_id: str,
    source: str,
    title: str,
    container: str,
    tags: list[str],
    doc_type: str,
) -> None:
    if title:
        _remember_source_fact(
            user_id,
            source,
            "projects",
            f"{source} file/note touched: {title}.",
            f"{source} file metadata",
        )
    if container:
        _remember_source_fact(
            user_id,
            source,
            "projects",
            f"{source} workspace/folder in use: {container}.",
            f"{source} container metadata",
        )
    if doc_type:
        _remember_source_fact(
            user_id,
            source,
            "preferences",
            f"{source} document type used: {doc_type}.",
            f"{source} document metadata",
        )
    for tag in tags[:8]:
        _remember_source_fact(
            user_id,
            source,
            "scratchpad",
            f"{source} knowledge tag/topic: {tag}.",
            f"{source} tag metadata",
        )


def _remember_source_fact(user_id: str, source: str, scope: str, fact: str, reason: str) -> None:
    fact = " ".join(str(fact).split()).strip()
    if not fact:
        return
    propose_memory_diff(
        user_id=user_id,
        scope=scope,
        proposed_content=fact,
        reason=reason,
        source=source,
    )


def _drive_doc_type(mime_type: str) -> str:
    value = mime_type.lower()
    if "spreadsheet" in value:
        return "spreadsheet"
    if "presentation" in value:
        return "presentation"
    if "folder" in value:
        return "folder"
    if "pdf" in value:
        return "pdf"
    if "document" in value or "text" in value:
        return "document"
    return _feature_token(mime_type.split("/")[-1] if "/" in mime_type else mime_type)


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
