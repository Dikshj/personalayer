"""Cloud storage and design-tool API clients."""

import httpx

DROPBOX_BASE = "https://api.dropboxapi.com/2"
GRAPH_BASE = "https://graph.microsoft.com/v1.0"
FIGMA_BASE = "https://api.figma.com/v1"


def fetch_dropbox_activity(access_token: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    response = httpx.post(f"{DROPBOX_BASE}/files/list_folder", json={"path": "", "recursive": False, "limit": 50}, headers=headers, timeout=10)
    response.raise_for_status()
    files = []
    for item in response.json().get("entries", []):
        files.append({
            "id": item.get("id"),
            "tag": item.get(".tag"),
            "client_modified": item.get("client_modified"),
            "server_modified": item.get("server_modified"),
        })
    return {"files": files}


def fetch_onedrive_activity(access_token: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    response = httpx.get(f"{GRAPH_BASE}/me/drive/recent", headers=headers, timeout=10)
    response.raise_for_status()
    files = []
    for item in response.json().get("value", []):
        files.append({
            "id": item.get("id"),
            "mime_type": (item.get("file") or {}).get("mimeType", "folder" if item.get("folder") else "other"),
            "modified_at": item.get("lastModifiedDateTime"),
            "is_shared": bool(item.get("shared")),
        })
    return {"files": files}


def fetch_figma_files(access_token: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    response = httpx.get(f"{FIGMA_BASE}/me", headers=headers, timeout=10)
    response.raise_for_status()
    profile = response.json()
    return {"profile": {"id": profile.get("id"), "team_count": 0}}

