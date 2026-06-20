"""Notion API client."""

import httpx

NOTION_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def fetch_notion_pages(access_token: str, max_results: int = 50, start_cursor: str | None = None) -> dict:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    body: dict[str, object] = {
        "page_size": min(max_results, 100),
        "filter": {"value": "page", "property": "object"},
    }
    if start_cursor:
        body["start_cursor"] = start_cursor

    response = httpx.post(f"{NOTION_BASE}/search", json=body, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()

    pages = []
    for result in data.get("results", []):
        props = result.get("properties", {})
        title_prop = props.get("title") or props.get("Name") or {}
        title_items = title_prop.get("title", []) if isinstance(title_prop, dict) else []
        title_length = sum(len(item.get("plain_text", "")) for item in title_items)
        pages.append({
            "id": result.get("id"),
            "object_type": result.get("object", "page"),
            "title_length": title_length,
            "has_content": title_length > 0,
            "last_edited_time": result.get("last_edited_time"),
            "created_time": result.get("created_time"),
            "parent_type": result.get("parent", {}).get("type"),
            "workspace": bool(result.get("parent", {}).get("workspace", False)),
        })

    return {
        "pages": pages,
        "next_cursor": data.get("next_cursor"),
        "has_more": data.get("has_more", False),
    }

