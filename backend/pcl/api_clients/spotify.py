"""Spotify API client."""

import httpx

SPOTIFY_BASE = "https://api.spotify.com/v1"


def fetch_recently_played(access_token: str, limit: int = 50, after_ms: int | None = None) -> dict:
    params: dict[str, object] = {"limit": min(limit, 50)}
    if after_ms:
        params["after"] = after_ms

    headers = {"Authorization": f"Bearer {access_token}"}
    response = httpx.get(f"{SPOTIFY_BASE}/me/player/recently-played", params=params, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()

    tracks = []
    for item in data.get("items", []):
        track = item.get("track", {})
        tracks.append({
            "played_at": item.get("played_at"),
            "duration_ms": track.get("duration_ms", 0),
            "explicit": track.get("explicit", False),
            "popularity": track.get("popularity", 0),
            "artist_count": len(track.get("artists", [])),
        })

    return {"tracks": tracks, "next_after": data.get("cursors", {}).get("after")}


def fetch_top_genres(access_token: str, time_range: str = "medium_term") -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    response = httpx.get(
        f"{SPOTIFY_BASE}/me/top/artists",
        params={"limit": 20, "time_range": time_range},
        headers=headers,
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()

    genre_counts: dict[str, int] = {}
    for artist in data.get("items", []):
        for genre in artist.get("genres", []):
            genre_counts[genre] = genre_counts.get(genre, 0) + 1
    return {"genre_counts": genre_counts}

