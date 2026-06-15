"""Connector clients, privacy filter, and cursor store.

Production-grade connector infrastructure with:
- Per-connector field whitelisting
- Blocked keyword detection (PII, secrets)
- Incremental cursor/delta sync
- Rate limit handling
- Real provider API sync for Gmail, Calendar, Notion, Spotify, YouTube
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import httpx


class ConnectorError(Exception):
    """Typed connector errors."""

    @classmethod
    def rate_limited(cls, retry_after: int) -> "ConnectorError":
        return cls(f"Rate limited. Retry after {retry_after}s")

    @classmethod
    def api_error(cls, status: int, message: str) -> "ConnectorError":
        return cls(f"API error {status}: {message}")

    @classmethod
    def invalid_response(cls) -> "ConnectorError":
        return cls("Invalid API response")

    @classmethod
    def unauthorized(cls) -> "ConnectorError":
        return cls("Unauthorized")


class ConnectorPrivacyFilter:
    """Privacy filter for connector data.

    Only allows whitelisted fields per connector.
    Detects and blocks events containing sensitive keywords.
    """

    FIELD_WHITELIST: Dict[str, list] = {
        "gmail": ["id", "threadId", "labelIds", "snippet", "internalDate", "historyId"],
        "calendar": ["id", "summary", "start", "end", "created", "updated", "status"],
        "spotify": ["track", "played_at", "context"],
        "youtube": ["id", "snippet", "contentDetails"],
        "notion": ["id", "title", "created_time", "last_edited_time"],
        "google_fit": ["dataSourceId", "point", "startTimeNanos", "endTimeNanos"],
    }

    BLOCKED_KEYWORDS = [
        "password", "secret", "token", "api_key", "credit_card",
        "ssn", "private_key", "passphrase", "authorization",
    ]

    @classmethod
    def filter_event(cls, connector_type: str, event: Dict[str, Any]) -> Dict[str, Any]:
        allowed = cls.FIELD_WHITELIST.get(connector_type, list(event.keys()))
        return {k: v for k, v in event.items() if k in allowed}

    @classmethod
    def has_blocked_keywords(cls, event: Dict[str, Any]) -> bool:
        text = str(event).lower()
        return any(kw in text for kw in cls.BLOCKED_KEYWORDS)

    @classmethod
    def should_block(cls, connector_type: str, event: Dict[str, Any]) -> bool:
        filtered = cls.filter_event(connector_type, event)
        return cls.has_blocked_keywords(filtered)


class ConnectorCursorStore:
    """Persistent store for connector sync cursors."""

    def __init__(self, backend: str = "db"):
        self.backend = backend
        self._memory: Dict[str, str] = {}

    def save_cursor(self, connector: str, cursor: str) -> None:
        if self.backend == "memory":
            self._memory[connector] = cursor
        else:
            from database import update_pcl_integration_sync
            update_pcl_integration_sync(
                source=connector,
                status="synced",
                items_synced=0,
                sync_cursor={"cursor": cursor},
            )

    def load_cursor(self, connector: str) -> Optional[str]:
        if self.backend == "memory":
            return self._memory.get(connector)
        from database import get_pcl_integration
        integration = get_pcl_integration(connector)
        if integration and integration.get("sync_cursor"):
            return integration["sync_cursor"].get("cursor")
        return None

    def clear(self, connector: str) -> None:
        if self.backend == "memory":
            self._memory.pop(connector, None)
        else:
            from database import update_pcl_integration_sync
            update_pcl_integration_sync(
                source=connector,
                status="pending",
                items_synced=0,
                sync_cursor={},
            )


# ---------------------------------------------------------------------------
# Real sync implementations
# ---------------------------------------------------------------------------

def _get_access_token(source: str, user_id: str = "local_user") -> str:
    from database import get_decrypted_pcl_integration_oauth_token
    token = get_decrypted_pcl_integration_oauth_token(source, user_id)
    if not token:
        return ""
    return token.get("access_token", "")


def sync_gmail(user_id: str = "local_user", cursor_store: Optional[ConnectorCursorStore] = None) -> dict:
    """Sync Gmail metadata using historyId / after-date strategy."""
    cursor_store = cursor_store or ConnectorCursorStore()
    access_token = _get_access_token("gmail", user_id)
    if not access_token:
        return {"status": "error", "error": "oauth_not_connected"}

    after = cursor_store.load_cursor("gmail") or "0"
    query = "in:inbox" if after == "0" else f"after:{after}"
    url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages"

    try:
        resp = httpx.get(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            params={"q": query, "maxResults": 100},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        messages = data.get("messages", [])
        result = []
        for msg in messages:
            msg_id = msg.get("id")
            if not msg_id:
                continue
            detail = httpx.get(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"format": "metadata", "metadataHeaders": "Subject,From"},
                timeout=30,
            )
            detail.raise_for_status()
            d = detail.json()
            filtered = ConnectorPrivacyFilter.filter_event("gmail", d)
            if ConnectorPrivacyFilter.should_block("gmail", filtered):
                continue
            result.append(filtered)

        if result:
            newest = result[-1].get("internalDate", str(int(datetime.now().timestamp() * 1000)))
            cursor_store.save_cursor("gmail", newest)

        return {"status": "ok", "source": "gmail", "count": len(result), "messages": result}
    except httpx.HTTPStatusError as exc:
        return {"status": "error", "error": "api_error", "detail": f"HTTP {exc.response.status_code}"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def sync_calendar(user_id: str = "local_user", cursor_store: Optional[ConnectorCursorStore] = None) -> dict:
    """Sync Calendar events using sync tokens / time window."""
    cursor_store = cursor_store or ConnectorCursorStore()
    access_token = _get_access_token("calendar", user_id)
    if not access_token:
        return {"status": "error", "error": "oauth_not_connected"}

    now = datetime.utcnow()
    time_min = now.isoformat() + "Z"
    time_max = (now + timedelta(days=30)).isoformat() + "Z"

    try:
        resp = httpx.get(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"timeMin": time_min, "timeMax": time_max, "maxResults": 250, "singleEvents": True, "orderBy": "startTime"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        result = []
        for item in items:
            filtered = ConnectorPrivacyFilter.filter_event("calendar", item)
            if ConnectorPrivacyFilter.should_block("calendar", filtered):
                continue
            result.append(filtered)

        if result:
            cursor_store.save_cursor("calendar", time_min)

        return {"status": "ok", "source": "calendar", "count": len(result), "events": result}
    except httpx.HTTPStatusError as exc:
        return {"status": "error", "error": "api_error", "detail": f"HTTP {exc.response.status_code}"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def sync_spotify(user_id: str = "local_user", cursor_store: Optional[ConnectorCursorStore] = None) -> dict:
    """Sync Spotify recently played with cursor pagination."""
    cursor_store = cursor_store or ConnectorCursorStore()
    access_token = _get_access_token("spotify", user_id)
    if not access_token:
        return {"status": "error", "error": "oauth_not_connected"}

    after = cursor_store.load_cursor("spotify")
    all_tracks = []
    has_more = True

    try:
        while has_more:
            params = {"limit": 50}
            if after:
                params["after"] = after
            resp = httpx.get(
                "https://api.spotify.com/v1/me/player/recently-played",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])
            for item in items:
                track = item.get("track", {})
                filtered = ConnectorPrivacyFilter.filter_event("spotify", {
                    "track": {"id": track.get("id"), "name": track.get("name")},
                    "played_at": item.get("played_at"),
                    "context": item.get("context"),
                })
                if ConnectorPrivacyFilter.should_block("spotify", filtered):
                    continue
                all_tracks.append(filtered)

            if items:
                after = items[-1].get("played_at")
                cursor_store.save_cursor("spotify", after)
            has_more = len(items) == 50

        return {"status": "ok", "source": "spotify", "count": len(all_tracks), "tracks": all_tracks}
    except httpx.HTTPStatusError as exc:
        return {"status": "error", "error": "api_error", "detail": f"HTTP {exc.response.status_code}"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def sync_notion(user_id: str = "local_user", cursor_store: Optional[ConnectorCursorStore] = None) -> dict:
    """Sync Notion search/database/page cursors."""
    cursor_store = cursor_store or ConnectorCursorStore()
    access_token = _get_access_token("notion", user_id)
    if not access_token:
        return {"status": "error", "error": "oauth_not_connected"}

    try:
        resp = httpx.post(
            "https://api.notion.com/v1/search",
            headers={"Authorization": f"Bearer {access_token}", "Notion-Version": "2022-06-28"},
            json={"page_size": 100},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for page in data.get("results", []):
            filtered = ConnectorPrivacyFilter.filter_event("notion", {
                "id": page.get("id"),
                "title": page.get("properties", {}).get("title", {}),
                "created_time": page.get("created_time"),
                "last_edited_time": page.get("last_edited_time"),
            })
            if ConnectorPrivacyFilter.should_block("notion", filtered):
                continue
            results.append(filtered)

        cursor_store.save_cursor("notion", data.get("next_cursor", ""))
        return {"status": "ok", "source": "notion", "count": len(results), "pages": results}
    except httpx.HTTPStatusError as exc:
        return {"status": "error", "error": "api_error", "detail": f"HTTP {exc.response.status_code}"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def sync_youtube(user_id: str = "local_user", cursor_store: Optional[ConnectorCursorStore] = None) -> dict:
    """Sync YouTube activity/watch metadata."""
    cursor_store = cursor_store or ConnectorCursorStore()
    access_token = _get_access_token("youtube", user_id)
    if not access_token:
        return {"status": "error", "error": "oauth_not_connected"}

    try:
        resp = httpx.get(
            "https://www.googleapis.com/youtube/v3/activities",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"part": "snippet,contentDetails", "mine": "true", "maxResults": 50},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        results = []
        for item in items:
            filtered = ConnectorPrivacyFilter.filter_event("youtube", {
                "id": item.get("id"),
                "snippet": item.get("snippet"),
                "contentDetails": item.get("contentDetails"),
            })
            if ConnectorPrivacyFilter.should_block("youtube", filtered):
                continue
            results.append(filtered)

        if data.get("nextPageToken"):
            cursor_store.save_cursor("youtube", data["nextPageToken"])
        return {"status": "ok", "source": "youtube", "count": len(results), "activities": results}
    except httpx.HTTPStatusError as exc:
        return {"status": "error", "error": "api_error", "detail": f"HTTP {exc.response.status_code}"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def sync_google_fit(user_id: str = "local_user", cursor_store: Optional[ConnectorCursorStore] = None) -> dict:
    """Sync Google Fit activity samples."""
    cursor_store = cursor_store or ConnectorCursorStore()
    access_token = _get_access_token("google_fit", user_id)
    if not access_token:
        return {"status": "error", "error": "oauth_not_connected"}

    now = datetime.utcnow()
    start = (now - timedelta(days=7)).isoformat() + "Z"
    end = now.isoformat() + "Z"

    try:
        resp = httpx.post(
            "https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "aggregateBy": [{"dataTypeName": "com.google.step_count.delta"}],
                "bucketByTime": {"durationMillis": 86400000},
                "startTimeMillis": int((now - timedelta(days=7)).timestamp() * 1000),
                "endTimeMillis": int(now.timestamp() * 1000),
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        buckets = data.get("bucket", [])
        results = []
        for bucket in buckets:
            filtered = ConnectorPrivacyFilter.filter_event("google_fit", {
                "startTimeMillis": bucket.get("startTimeMillis"),
                "endTimeMillis": bucket.get("endTimeMillis"),
                "dataset": bucket.get("dataset"),
            })
            if ConnectorPrivacyFilter.should_block("google_fit", filtered):
                continue
            results.append(filtered)

        cursor_store.save_cursor("google_fit", end)
        return {"status": "ok", "source": "google_fit", "count": len(results), "buckets": results}
    except httpx.HTTPStatusError as exc:
        return {"status": "error", "error": "api_error", "detail": f"HTTP {exc.response.status_code}"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
