FIRST_PARTY_INTEGRATIONS = {
    "gmail": {
        "name": "Gmail",
        "scopes": ["email_metadata", "labels", "thread_timing"],
        "description": "Email behavior signals without storing raw message content.",
    },
    "calendar": {
        "name": "Calendar",
        "scopes": ["event_metadata", "availability_patterns"],
        "description": "Work rhythm, meeting load, and planning behavior.",
    },
    "notion": {
        "name": "Notion",
        "scopes": ["workspace_metadata", "page_activity"],
        "description": "Project and knowledge-work signals without raw page storage.",
    },
    "github": {
        "name": "GitHub",
        "scopes": ["public_activity", "stars", "repository_metadata"],
        "description": "Developer interests, tools, and active projects.",
    },
    "spotify": {
        "name": "Spotify",
        "scopes": ["recently_played", "session_timing", "genre_patterns"],
        "description": "Focus rhythm and listening-session metadata without storing track content.",
    },
    "youtube": {
        "name": "YouTube",
        "scopes": ["watch_metadata", "category_patterns"],
        "description": "Watch category and session metadata without storing transcripts or raw video content.",
    },
    "apple_health": {
        "name": "Apple Health",
        "scopes": ["activity_metadata", "sleep_timing", "workout_patterns"],
        "description": "Daily activity and recovery metadata without storing medical notes.",
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
    }
