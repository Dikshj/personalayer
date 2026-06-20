"""Google API clients: Gmail, Calendar, Drive, and YouTube."""

from datetime import datetime, timezone
from typing import Optional

import httpx

GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1"
CALENDAR_BASE = "https://www.googleapis.com/calendar/v3"
DRIVE_BASE = "https://www.googleapis.com/drive/v3"
YOUTUBE_BASE = "https://www.googleapis.com/youtube/v3"


def fetch_gmail_messages(
    access_token: str,
    max_results: int = 50,
    page_token: Optional[str] = None,
) -> dict:
    params: dict[str, object] = {
        "maxResults": max_results,
        "fields": "messages(id,threadId),nextPageToken",
    }
    if page_token:
        params["pageToken"] = page_token

    headers = {"Authorization": f"Bearer {access_token}"}
    response = httpx.get(f"{GMAIL_BASE}/users/me/messages", params=params, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()

    messages = []
    for item in data.get("messages", [])[:max_results]:
        message_id = item.get("id")
        if not message_id:
            continue
        detail = httpx.get(
            f"{GMAIL_BASE}/users/me/messages/{message_id}",
            params={
                "format": "metadata",
                "metadataHeaders": ["From", "Subject"],
                "fields": "id,threadId,labelIds,internalDate,payload/headers",
            },
            headers=headers,
            timeout=10,
        )
        if detail.status_code != 200:
            continue
        msg = detail.json()
        headers_map = {
            header.get("name", ""): header.get("value", "")
            for header in msg.get("payload", {}).get("headers", [])
        }
        sender = headers_map.get("From", "")
        sender_domain = sender.split("@")[-1].split(">")[0].strip().lower() if sender else ""
        messages.append({
            "id": msg.get("id"),
            "thread_id": msg.get("threadId"),
            "labels": msg.get("labelIds", []),
            "timestamp": int(msg.get("internalDate", 0) or 0),
            "sender_domain": sender_domain,
            "has_attachments": "ATTACHMENT" in str(msg.get("labelIds", [])),
        })

    return {"messages": messages, "next_page_token": data.get("nextPageToken")}


def fetch_calendar_events(
    access_token: str,
    max_results: int = 100,
    sync_token: Optional[str] = None,
    time_min: Optional[str] = None,
) -> dict:
    params: dict[str, object] = {
        "maxResults": max_results,
        "singleEvents": True,
        "orderBy": "startTime",
        "fields": "items(id,summary,start,end,attendees,status,organizer),nextSyncToken,nextPageToken",
    }
    if sync_token:
        params = {"syncToken": sync_token}
    elif time_min:
        params["timeMin"] = time_min

    headers = {"Authorization": f"Bearer {access_token}"}
    response = httpx.get(f"{CALENDAR_BASE}/calendars/primary/events", params=params, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()

    events = []
    for event in data.get("items", []):
        start = event.get("start", {})
        end = event.get("end", {})
        events.append({
            "id": event.get("id"),
            "title_length": len(event.get("summary", "")),
            "start": start.get("dateTime") or start.get("date", ""),
            "end": end.get("dateTime") or end.get("date", ""),
            "attendee_count": len(event.get("attendees", [])),
            "is_organizer": event.get("organizer", {}).get("self", False),
            "status": event.get("status"),
        })

    return {
        "events": events,
        "next_sync_token": data.get("nextSyncToken"),
        "next_page_token": data.get("nextPageToken"),
    }


def fetch_drive_activity(access_token: str, max_results: int = 50) -> dict:
    params = {
        "pageSize": max_results,
        "fields": "files(id,name,mimeType,modifiedTime,viewedByMeTime,shared)",
        "orderBy": "modifiedTime desc",
    }
    headers = {"Authorization": f"Bearer {access_token}"}
    response = httpx.get(f"{DRIVE_BASE}/files", params=params, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()

    files = []
    for item in data.get("files", []):
        mime = item.get("mimeType", "")
        files.append({
            "id": item.get("id"),
            "mime_type": mime,
            "file_category": _categorize_mime(mime),
            "modified_at": item.get("modifiedTime"),
            "viewed_at": item.get("viewedByMeTime"),
            "is_shared": item.get("shared", False),
        })
    return {"files": files}


def fetch_youtube_activity(access_token: str, max_results: int = 50) -> dict:
    """Fetch privacy-preserving YouTube account activity metadata.

    The public YouTube Data API does not expose full watch history. This fetches
    the authenticated user's uploaded/liked playlist activity where available,
    enough to infer category/topic patterns without storing titles.
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    channels = httpx.get(
        f"{YOUTUBE_BASE}/channels",
        params={"part": "contentDetails", "mine": "true", "maxResults": 1},
        headers=headers,
        timeout=10,
    )
    channels.raise_for_status()
    channel_items = channels.json().get("items", [])
    uploads = (
        channel_items[0]
        .get("contentDetails", {})
        .get("relatedPlaylists", {})
        .get("uploads")
        if channel_items
        else None
    )
    if not uploads:
        return {"videos": []}

    playlist = httpx.get(
        f"{YOUTUBE_BASE}/playlistItems",
        params={"part": "snippet,contentDetails", "playlistId": uploads, "maxResults": min(max_results, 50)},
        headers=headers,
        timeout=10,
    )
    playlist.raise_for_status()

    videos = []
    for item in playlist.json().get("items", []):
        snippet = item.get("snippet", {})
        videos.append({
            "id": item.get("contentDetails", {}).get("videoId"),
            "category": "uploaded_video",
            "duration_minutes": 0,
            "watched_at": snippet.get("publishedAt") or datetime.now(timezone.utc).isoformat(),
        })
    return {"videos": videos}


def _categorize_mime(mime: str) -> str:
    if "document" in mime:
        return "doc"
    if "spreadsheet" in mime:
        return "spreadsheet"
    if "presentation" in mime:
        return "slides"
    if "pdf" in mime:
        return "pdf"
    if "image" in mime:
        return "image"
    if "video" in mime:
        return "video"
    if "audio" in mime:
        return "audio"
    if "folder" in mime:
        return "folder"
    return "other"

