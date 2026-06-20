"""Reddit API client."""

import httpx

REDDIT_BASE = "https://oauth.reddit.com"


def fetch_reddit_activity(access_token: str, limit: int = 50) -> dict:
    headers = {"Authorization": f"Bearer {access_token}", "User-Agent": "PersonaLayer/1.0"}
    response = httpx.get(f"{REDDIT_BASE}/user/me/overview", params={"limit": min(limit, 100)}, headers=headers, timeout=10)
    response.raise_for_status()
    items = []
    for child in response.json().get("data", {}).get("children", []):
        data = child.get("data", {})
        items.append({
            "kind": child.get("kind"),
            "subreddit": data.get("subreddit"),
            "created_utc": data.get("created_utc"),
            "score_bucket": _score_bucket(data.get("score", 0)),
        })
    return {"items": items}


def _score_bucket(score: int) -> str:
    if score >= 100:
        return "high"
    if score >= 10:
        return "medium"
    return "low"

