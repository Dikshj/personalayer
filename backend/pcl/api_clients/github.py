"""GitHub API client."""

import httpx

GITHUB_BASE = "https://api.github.com"


def fetch_user_events(username: str, access_token: str | None = None, max_pages: int = 2) -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    events = []
    for page in range(1, max_pages + 1):
        response = httpx.get(
            f"{GITHUB_BASE}/users/{username}/events/public",
            params={"per_page": 30, "page": page},
            headers=headers,
            timeout=10,
        )
        if response.status_code != 200:
            break
        page_events = response.json()
        if not page_events:
            break
        for event in page_events:
            events.append({
                "type": event.get("type"),
                "repo": event.get("repo", {}).get("name", ""),
                "created_at": event.get("created_at"),
                "public": event.get("public", True),
            })

    return {"events": events}


def fetch_starred_repos(username: str, access_token: str | None = None) -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    response = httpx.get(f"{GITHUB_BASE}/users/{username}/starred", params={"per_page": 50}, headers=headers, timeout=10)
    response.raise_for_status()

    return {
        "repos": [
            {
                "language": repo.get("language"),
                "topics": repo.get("topics", []),
                "starred_at": repo.get("updated_at"),
            }
            for repo in response.json()
        ]
    }

