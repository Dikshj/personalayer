FIRST_PARTY_INTEGRATIONS = {
    "gmail": {
        "name": "Gmail",
        "scopes": ["email_metadata", "labels", "thread_timing"],
        "description": "Email behavior signals without storing raw message content.",
        "auth_type": "oauth_or_local_metadata",
        "metadata_example": {
            "messages": [{
                "labels": ["Work"],
                "thread_size": 2,
                "has_attachments": False,
                "timestamp": 1700000000000,
            }],
        },
        "oauth": {
            "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "client_id_env": "GOOGLE_OAUTH_CLIENT_ID",
            "scopes": [
                "https://www.googleapis.com/auth/gmail.metadata",
            ],
        },
    },
    "calendar": {
        "name": "Calendar",
        "scopes": ["event_metadata", "availability_patterns"],
        "description": "Work rhythm, meeting load, and planning behavior.",
        "auth_type": "oauth_or_local_metadata",
        "metadata_example": {
            "events": [{
                "start": "2026-05-11T10:00:00Z",
                "duration_minutes": 45,
                "attendee_count": 3,
            }],
        },
        "oauth": {
            "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "client_id_env": "GOOGLE_OAUTH_CLIENT_ID",
            "scopes": [
                "https://www.googleapis.com/auth/calendar.readonly",
            ],
        },
    },
    "notion": {
        "name": "Notion",
        "scopes": ["workspace_metadata", "page_activity"],
        "description": "Project and knowledge-work signals without raw page storage.",
        "auth_type": "oauth_or_local_metadata",
        "metadata_example": {
            "pages": [{
                "workspace": "Product",
                "object_type": "project",
                "tags": ["Roadmap"],
                "last_edited_time": "2026-05-11T12:00:00Z",
            }],
        },
        "oauth": {
            "authorize_url": "https://api.notion.com/v1/oauth/authorize",
            "client_id_env": "NOTION_OAUTH_CLIENT_ID",
            "scopes": [],
        },
    },
    "github": {
        "name": "GitHub",
        "scopes": ["public_activity", "stars", "repository_metadata"],
        "description": "Developer interests, tools, and active projects.",
        "auth_type": "public_username",
        "metadata_example": {"username": "octocat"},
        "oauth": None,
    },
    "spotify": {
        "name": "Spotify",
        "scopes": ["recently_played", "session_timing", "genre_patterns"],
        "description": "Focus rhythm and listening-session metadata without storing track content.",
        "auth_type": "oauth_or_local_metadata",
        "metadata_example": {
            "recently_played": [{
                "played_at": "2026-05-11T08:00:00Z",
                "duration_minutes": 45,
                "genres": ["Focus"],
            }],
        },
        "oauth": {
            "authorize_url": "https://accounts.spotify.com/authorize",
            "client_id_env": "SPOTIFY_OAUTH_CLIENT_ID",
            "scopes": ["user-read-recently-played"],
        },
    },
    "youtube": {
        "name": "YouTube",
        "scopes": ["watch_metadata", "category_patterns"],
        "description": "Watch category and session metadata without storing transcripts or raw video content.",
        "auth_type": "oauth_or_local_metadata",
        "metadata_example": {
            "watch_history": [{
                "watched_at": "2026-05-11T20:00:00Z",
                "category": "AI Tutorial",
                "duration_minutes": 25,
            }],
        },
        "oauth": {
            "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "client_id_env": "GOOGLE_OAUTH_CLIENT_ID",
            "scopes": [
                "https://www.googleapis.com/auth/youtube.readonly",
            ],
        },
    },
    "apple_health": {
        "name": "Apple Health",
        "scopes": ["activity_metadata", "sleep_timing", "workout_patterns"],
        "description": "Daily activity and recovery metadata without storing medical notes.",
        "auth_type": "local_metadata",
        "metadata_example": {
            "activity": [{
                "date": "2026-05-11T06:00:00Z",
                "active_minutes": 42,
                "stand_hours": 9,
                "sleep_hours": 7.5,
            }],
        },
        "oauth": None,
    },
}


def integration_catalog() -> list[dict]:
    return [
        {"source": source, **config}
        for source, config in FIRST_PARTY_INTEGRATIONS.items()
    ]


def default_integration(source: str) -> dict:
    config = FIRST_PARTY_INTEGRATIONS.get(source)
    if not config:
        raise ValueError("unknown_integration")
    return {
        "source": source,
        "name": config["name"],
        "scopes": config["scopes"],
        "description": config["description"],
        "auth_type": config["auth_type"],
        "metadata_example": config["metadata_example"],
        "oauth": config["oauth"],
    }
