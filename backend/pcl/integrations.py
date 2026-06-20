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
            "token_url": "https://oauth2.googleapis.com/token",
            "client_id_env": "GOOGLE_OAUTH_CLIENT_ID",
            "client_secret_env": "GOOGLE_OAUTH_CLIENT_SECRET",
            "scopes": [
                "https://www.googleapis.com/auth/gmail.readonly",
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
            "token_url": "https://oauth2.googleapis.com/token",
            "client_id_env": "GOOGLE_OAUTH_CLIENT_ID",
            "client_secret_env": "GOOGLE_OAUTH_CLIENT_SECRET",
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
            "token_url": "https://api.notion.com/v1/oauth/token",
            "client_id_env": "NOTION_OAUTH_CLIENT_ID",
            "client_secret_env": "NOTION_OAUTH_CLIENT_SECRET",
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
            "token_url": "https://accounts.spotify.com/api/token",
            "client_id_env": "SPOTIFY_OAUTH_CLIENT_ID",
            "client_secret_env": "SPOTIFY_OAUTH_CLIENT_SECRET",
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
            "token_url": "https://oauth2.googleapis.com/token",
            "client_id_env": "GOOGLE_OAUTH_CLIENT_ID",
            "client_secret_env": "GOOGLE_OAUTH_CLIENT_SECRET",
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
    "google_drive": {
        "name": "Google Drive",
        "scopes": ["file_metadata", "folder_activity", "edit_timing"],
        "description": "Document and project activity metadata without storing raw file contents.",
        "auth_type": "oauth_or_local_metadata",
        "metadata_example": {
            "files": [{
                "mime_type": "application/vnd.google-apps.document",
                "folder": "Product",
                "last_edited_time": "2026-05-11T12:30:00Z",
                "owner_domain": "example.com",
            }],
        },
        "oauth": {
            "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "client_id_env": "GOOGLE_OAUTH_CLIENT_ID",
            "client_secret_env": "GOOGLE_OAUTH_CLIENT_SECRET",
            "scopes": [
                "https://www.googleapis.com/auth/drive.metadata.readonly",
            ],
        },
    },
    "slack": {
        "name": "Slack",
        "scopes": ["channel_activity", "message_count_patterns"],
        "description": "Communication patterns and workspace activity without message content.",
        "auth_type": "oauth",
        "metadata_example": {},
        "oauth": {
            "authorize_url": "https://slack.com/oauth/v2/authorize",
            "token_url": "https://slack.com/api/oauth.v2.access",
            "client_id_env": "SLACK_OAUTH_CLIENT_ID",
            "client_secret_env": "SLACK_OAUTH_CLIENT_SECRET",
            "scopes": ["channels:read", "channels:history", "groups:read", "groups:history"],
        },
    },
    "linear": {
        "name": "Linear",
        "scopes": ["issue_patterns", "completion_rate", "priority_signals"],
        "description": "Work patterns, issue velocity, and priority behavior.",
        "auth_type": "oauth",
        "metadata_example": {},
        "oauth": {
            "authorize_url": "https://linear.app/oauth/authorize",
            "token_url": "https://api.linear.app/oauth/token",
            "client_id_env": "LINEAR_OAUTH_CLIENT_ID",
            "client_secret_env": "LINEAR_OAUTH_CLIENT_SECRET",
            "scopes": ["read"],
        },
    },
    "jira": {
        "name": "Jira",
        "scopes": ["issue_patterns", "priority_signals", "project_activity"],
        "description": "Issue state, priority, and work management metadata.",
        "auth_type": "oauth",
        "metadata_example": {"cloud_id": "required-atlassian-cloud-id"},
        "oauth": {
            "authorize_url": "https://auth.atlassian.com/authorize",
            "token_url": "https://auth.atlassian.com/oauth/token",
            "client_id_env": "JIRA_OAUTH_CLIENT_ID",
            "client_secret_env": "JIRA_OAUTH_CLIENT_SECRET",
            "scopes": ["read:jira-work", "read:jira-user"],
        },
    },
    "todoist": {
        "name": "Todoist",
        "scopes": ["task_completion_patterns", "project_activity"],
        "description": "Task completion velocity and project organization patterns.",
        "auth_type": "oauth",
        "metadata_example": {},
        "oauth": {
            "authorize_url": "https://todoist.com/oauth/authorize",
            "token_url": "https://todoist.com/oauth/access_token",
            "client_id_env": "TODOIST_OAUTH_CLIENT_ID",
            "client_secret_env": "TODOIST_OAUTH_CLIENT_SECRET",
            "scopes": ["data:read"],
        },
    },
    "strava": {
        "name": "Strava",
        "scopes": ["activity_patterns", "fitness_signals"],
        "description": "Exercise type, frequency, and physical activity rhythm.",
        "auth_type": "oauth",
        "metadata_example": {},
        "oauth": {
            "authorize_url": "https://www.strava.com/oauth/authorize",
            "token_url": "https://www.strava.com/oauth/token",
            "client_id_env": "STRAVA_OAUTH_CLIENT_ID",
            "client_secret_env": "STRAVA_OAUTH_CLIENT_SECRET",
            "scopes": ["activity:read"],
        },
    },
    "reddit": {
        "name": "Reddit",
        "scopes": ["community_activity", "topic_patterns"],
        "description": "Community and topic activity metadata without raw post content.",
        "auth_type": "oauth",
        "metadata_example": {},
        "oauth": {
            "authorize_url": "https://www.reddit.com/api/v1/authorize",
            "token_url": "https://www.reddit.com/api/v1/access_token",
            "client_id_env": "REDDIT_OAUTH_CLIENT_ID",
            "client_secret_env": "REDDIT_OAUTH_CLIENT_SECRET",
            "scopes": ["identity", "history"],
        },
    },
    "figma": {
        "name": "Figma",
        "scopes": ["design_tool_activity", "workspace_patterns"],
        "description": "Design tool account and workspace activity metadata.",
        "auth_type": "oauth",
        "metadata_example": {},
        "oauth": {
            "authorize_url": "https://www.figma.com/oauth",
            "token_url": "https://api.figma.com/v1/oauth/token",
            "client_id_env": "FIGMA_OAUTH_CLIENT_ID",
            "client_secret_env": "FIGMA_OAUTH_CLIENT_SECRET",
            "scopes": ["files:read"],
        },
    },
    "dropbox": {
        "name": "Dropbox",
        "scopes": ["file_metadata", "document_activity"],
        "description": "Cloud file metadata and modification patterns without file contents.",
        "auth_type": "oauth",
        "metadata_example": {},
        "oauth": {
            "authorize_url": "https://www.dropbox.com/oauth2/authorize",
            "token_url": "https://api.dropboxapi.com/oauth2/token",
            "client_id_env": "DROPBOX_OAUTH_CLIENT_ID",
            "client_secret_env": "DROPBOX_OAUTH_CLIENT_SECRET",
            "scopes": ["files.metadata.read"],
        },
    },
    "onedrive": {
        "name": "OneDrive",
        "scopes": ["file_metadata", "document_activity"],
        "description": "Microsoft Drive file metadata and recent document patterns.",
        "auth_type": "oauth",
        "metadata_example": {},
        "oauth": {
            "authorize_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            "client_id_env": "MICROSOFT_OAUTH_CLIENT_ID",
            "client_secret_env": "MICROSOFT_OAUTH_CLIENT_SECRET",
            "scopes": ["Files.Read", "offline_access"],
        },
    },
    "trello": {
        "name": "Trello",
        "scopes": ["card_activity", "project_activity"],
        "description": "Card, board, and task organization metadata.",
        "auth_type": "oauth",
        "metadata_example": {"api_key": "optional-trello-api-key"},
        "oauth": {
            "authorize_url": "https://trello.com/1/authorize",
            "token_url": "https://trello.com/1/OAuthGetAccessToken",
            "client_id_env": "TRELLO_OAUTH_CLIENT_ID",
            "client_secret_env": "TRELLO_OAUTH_CLIENT_SECRET",
            "scopes": ["read"],
        },
    },
    "asana": {
        "name": "Asana",
        "scopes": ["task_activity", "project_activity"],
        "description": "Task and project activity metadata.",
        "auth_type": "oauth",
        "metadata_example": {},
        "oauth": {
            "authorize_url": "https://app.asana.com/-/oauth_authorize",
            "token_url": "https://app.asana.com/-/oauth_token",
            "client_id_env": "ASANA_OAUTH_CLIENT_ID",
            "client_secret_env": "ASANA_OAUTH_CLIENT_SECRET",
            "scopes": ["default"],
        },
    },
    "linkedin": {
        "name": "LinkedIn",
        "scopes": ["feed_activity", "profile_activity", "topic_patterns"],
        "description": "Professional feed and topic signals captured locally through the extension bridge.",
        "auth_type": "extension_bridge",
        "metadata_example": {
            "items": [{
                "content_type": "post",
                "topic": "go-to-market",
                "author_role": "founder",
                "timestamp": 1700000000000,
            }],
        },
        "oauth": None,
    },
    "x": {
        "name": "X",
        "scopes": ["feed_activity", "post_activity", "topic_patterns"],
        "description": "Public feed, topic, and creator signals captured locally through the extension bridge.",
        "auth_type": "extension_bridge",
        "metadata_example": {
            "items": [{
                "content_type": "post",
                "topic": "ai agents",
                "engagement": "read",
                "timestamp": 1700000000000,
            }],
        },
        "oauth": None,
    },
    "instagram": {
        "name": "Instagram",
        "scopes": ["feed_activity", "creator_activity", "topic_patterns"],
        "description": "Creator and topic signals captured locally through the extension bridge.",
        "auth_type": "extension_bridge",
        "metadata_example": {
            "items": [{
                "content_type": "reel",
                "topic": "productivity",
                "creator_category": "education",
                "timestamp": 1700000000000,
            }],
        },
        "oauth": None,
    },
    "chatgpt": {
        "name": "ChatGPT",
        "scopes": ["session_signals", "prompt_metadata", "workflow_patterns"],
        "description": "Local AI-assistant workflow signals captured through the extension bridge.",
        "auth_type": "extension_bridge",
        "metadata_example": {
            "sessions": [{
                "task_type": "writing",
                "prompt_length_bucket": "medium",
                "timestamp": 1700000000000,
            }],
        },
        "oauth": None,
    },
    "claude": {
        "name": "Claude",
        "scopes": ["session_signals", "prompt_metadata", "workflow_patterns"],
        "description": "Local Claude workflow signals captured through the extension bridge.",
        "auth_type": "extension_bridge",
        "metadata_example": {
            "sessions": [{
                "task_type": "research",
                "artifact_used": True,
                "timestamp": 1700000000000,
            }],
        },
        "oauth": None,
    },
    "perplexity": {
        "name": "Perplexity",
        "scopes": ["query_metadata", "research_topics", "session_signals"],
        "description": "Research query and topic signals captured locally through the extension bridge.",
        "auth_type": "extension_bridge",
        "metadata_example": {
            "queries": [{
                "topic": "market research",
                "source_count_bucket": "many",
                "timestamp": 1700000000000,
            }],
        },
        "oauth": None,
    },
    "opencode": {
        "name": "OpenCode",
        "scopes": ["coding_session", "prompt_metadata", "project_activity"],
        "description": "Coding-agent workflow signals from local OpenCode sessions.",
        "auth_type": "local_metadata",
        "metadata_example": {
            "sessions": [{
                "project": "personalayer",
                "task_type": "refactor",
                "timestamp": 1700000000000,
            }],
        },
        "oauth": None,
    },
    "cursor": {
        "name": "Cursor",
        "scopes": ["coding_session", "prompt_metadata", "project_activity"],
        "description": "IDE and coding-assistant workflow metadata from Cursor.",
        "auth_type": "local_metadata",
        "metadata_example": {
            "sessions": [{
                "project": "personalayer",
                "language": "python",
                "assistant_action": "edit",
                "timestamp": 1700000000000,
            }],
        },
        "oauth": None,
    },
    "gemini": {
        "name": "Gemini",
        "scopes": ["session_signals", "prompt_metadata", "workflow_patterns"],
        "description": "Gemini workflow signals captured locally through the extension bridge.",
        "auth_type": "extension_bridge",
        "metadata_example": {
            "sessions": [{
                "task_type": "planning",
                "timestamp": 1700000000000,
            }],
        },
        "oauth": None,
    },
    "grok": {
        "name": "Grok",
        "scopes": ["session_signals", "prompt_metadata", "workflow_patterns"],
        "description": "Grok workflow signals captured locally through the extension bridge.",
        "auth_type": "extension_bridge",
        "metadata_example": {
            "sessions": [{
                "task_type": "social_research",
                "timestamp": 1700000000000,
            }],
        },
        "oauth": None,
    },
    "github_copilot": {
        "name": "GitHub Copilot",
        "scopes": ["coding_session", "completion_activity", "project_activity"],
        "description": "Coding-assistant usage and project metadata from local IDE integrations.",
        "auth_type": "local_metadata",
        "metadata_example": {
            "sessions": [{
                "project": "personalayer",
                "language": "typescript",
                "completion_accepted": True,
                "timestamp": 1700000000000,
            }],
        },
        "oauth": None,
    },
    "aider": {
        "name": "Aider",
        "scopes": ["coding_session", "prompt_metadata", "project_activity"],
        "description": "Local coding-agent session metadata from Aider.",
        "auth_type": "local_metadata",
        "metadata_example": {
            "sessions": [{
                "project": "personalayer",
                "files_changed_bucket": "small",
                "timestamp": 1700000000000,
            }],
        },
        "oauth": None,
    },
    "terminal": {
        "name": "Terminal",
        "scopes": ["command_metadata", "project_activity", "workflow_patterns"],
        "description": "Local command and project metadata from shell wrappers.",
        "auth_type": "local_metadata",
        "metadata_example": {
            "commands": [{
                "project": "personalayer",
                "command_category": "test",
                "timestamp": 1700000000000,
            }],
        },
        "oauth": None,
    },
    "vscode": {
        "name": "VS Code",
        "scopes": ["project_activity", "extension_activity", "coding_session"],
        "description": "Local project, language, and editor workflow metadata from VS Code.",
        "auth_type": "local_metadata",
        "metadata_example": {
            "sessions": [{
                "project": "personalayer",
                "language": "python",
                "active_minutes": 45,
                "timestamp": 1700000000000,
            }],
        },
        "oauth": None,
    },
    "ide": {
        "name": "Generic IDE",
        "scopes": ["project_activity", "coding_session", "workflow_patterns"],
        "description": "Generic local IDE project and coding-session metadata.",
        "auth_type": "local_metadata",
        "metadata_example": {
            "sessions": [{
                "project": "personalayer",
                "language": "swift",
                "timestamp": 1700000000000,
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
