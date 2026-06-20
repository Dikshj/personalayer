"""Fitness API clients."""

import httpx

STRAVA_BASE = "https://www.strava.com/api/v3"


def fetch_strava_activities(access_token: str, per_page: int = 50, after: int | None = None) -> dict:
    params: dict[str, object] = {"per_page": min(per_page, 100)}
    if after:
        params["after"] = after
    headers = {"Authorization": f"Bearer {access_token}"}
    response = httpx.get(f"{STRAVA_BASE}/athlete/activities", params=params, headers=headers, timeout=10)
    response.raise_for_status()
    activities = []
    for activity in response.json():
        activities.append({
            "id": activity.get("id"),
            "type": activity.get("type"),
            "start_date": activity.get("start_date"),
            "moving_time": activity.get("moving_time", 0),
            "distance": activity.get("distance", 0),
            "elevation_gain": activity.get("total_elevation_gain", 0),
        })
    return {"activities": activities}

