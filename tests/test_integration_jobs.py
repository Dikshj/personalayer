import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


def test_github_integration_sync_uses_existing_collector(monkeypatch, tmp_path):
    import collectors.github
    import database

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'integration_jobs.db')
    database.create_tables()
    database.connect_pcl_integration(
        source="github",
        name="GitHub",
        scopes=["public_activity"],
        metadata={
            "username": "octocat",
            "repos": [
                {
                    "name": "personalayer",
                    "language": "Python",
                    "topics": ["FastAPI", "AI agents"],
                    "active": True,
                }
            ],
        },
    )
    monkeypatch.setattr(collectors.github, "collect_github", lambda username: 7)

    from pcl.integration_jobs import sync_integration
    result = sync_integration("github")

    assert result["status"] == "ok"
    assert result["items_synced"] == 7
    assert database.get_pcl_integration("github")["last_sync_status"] == "ok"
    assert database.get_pcl_integration("github")["items_synced"] == 7
    from pcl.memory import read_memory_file
    assert "GitHub repo tracked: personalayer (active)." in read_memory_file("local_user", "projects")["content"]
    assert "Uses Python in GitHub projects." in read_memory_file("local_user", "work-style")["content"]


def test_github_integration_requires_username(monkeypatch, tmp_path):
    import database

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'integration_jobs_missing_user.db')
    database.create_tables()
    database.connect_pcl_integration(
        source="github",
        name="GitHub",
        scopes=["public_activity"],
        metadata={},
    )

    from pcl.integration_jobs import sync_integration
    result = sync_integration("github")

    assert result["status"] == "error"
    assert result["error"] == "username_required"
    assert database.get_pcl_integration("github")["last_sync_status"] == "error"


def test_integration_missing_payload_schedules_retry(monkeypatch, tmp_path):
    import database

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'integration_jobs_retry.db')
    database.create_tables()
    database.connect_pcl_integration(
        source="gmail",
        name="Gmail",
        scopes=["email_metadata"],
        metadata={},
    )

    from pcl.integration_jobs import sync_integration
    first = sync_integration("gmail")
    second = sync_integration("gmail")
    integration = database.get_pcl_integration("gmail")

    assert first["status"] == "error"
    assert second["status"] == "skipped"
    assert second["reason"] == "next_sync_after_not_reached"
    assert integration["next_sync_after"]
    assert integration["sync_cursor"]["retry_count"] == 1
    assert "metadata.messages" in integration["sync_cursor"]["last_error"]


def test_sync_due_integrations_skips_until_next_sync_after(monkeypatch, tmp_path):
    import database
    from pcl.integration_jobs import _timestamp_ms, sync_due_integrations

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'integration_jobs_due_skip.db')
    database.create_tables()
    database.connect_pcl_integration(
        source="gmail",
        name="Gmail",
        scopes=["email_metadata"],
        metadata={"user_id": "user_1"},
        user_id="user_1",
    )
    database.update_pcl_integration_sync(
        source="gmail",
        status="error",
        next_sync_after=_timestamp_ms() + 60_000,
        sync_cursor={"retry_count": 1},
        user_id="user_1",
    )

    result = sync_due_integrations("user_1")

    assert result["skipped"] == 1
    assert result["results"][0]["status"] == "skipped"


def test_gmail_integration_sync_imports_metadata(monkeypatch, tmp_path):
    import database

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'integration_jobs_gmail.db')
    database.create_tables()
    database.connect_pcl_integration(
        source="gmail",
        name="Gmail",
        scopes=["email_metadata"],
        metadata={
            "messages": [
                {
                    "from": "person@example.com",
                    "sender": "Alex",
                    "subject": "PersonaLayer launch plan",
                    "project": "PersonaLayer",
                    "people": ["Maya"],
                    "labels": ["Work", "Important"],
                    "thread_size": 2,
                    "has_attachments": True,
                    "timestamp": 1700000000000,
                }
            ]
        },
    )

    from pcl.integration_jobs import sync_integration
    result = sync_integration("gmail")

    assert result["status"] == "ok"
    assert result["items_synced"] == 1
    assert database.get_pcl_integration("gmail")["last_sync_status"] == "ok"
    feed = database.get_feed_items_last_n_days(3650, source="gmail")
    assert len(feed) == 1
    assert "person@example.com" not in feed[0]["content"]
    signals = database.get_persona_signals_last_n_days(3650)
    assert any(signal["name"] == "email_label:work" for signal in signals)
    raw_events = database.list_raw_context_events("local_user")
    assert {event["feature_id"] for event in raw_events} >= {
        "label-work",
        "label-important",
        "attachment-heavy-email",
    }
    assert database.get_feature_signal("local_user", "gmail", "label-work")["usage_count"] == 1
    from pcl.memory import read_memory_file
    assert "Alex appears in Gmail conversations." in read_memory_file("local_user", "people")["content"]
    assert "Gmail mentions active project: PersonaLayer." in read_memory_file("local_user", "projects")["content"]
    assert "Gmail frequently uses label: work." in read_memory_file("local_user", "preferences")["content"]


def test_gmail_integration_sync_uses_incremental_cursor(monkeypatch, tmp_path):
    import database

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'integration_jobs_gmail_cursor.db')
    database.create_tables()
    database.connect_pcl_integration(
        source="gmail",
        name="Gmail",
        scopes=["email_metadata"],
        metadata={
            "messages": [
                {"labels": ["Work"], "thread_size": 1, "timestamp": 1700000000000},
                {"labels": ["Planning"], "thread_size": 1, "timestamp": 1700000100000},
            ]
        },
    )

    from pcl.integration_jobs import sync_integration
    first = sync_integration("gmail")
    second = sync_integration("gmail")

    assert first["items_synced"] == 2
    assert second["status"] == "ok"
    assert second["items_synced"] == 0
    integration = database.get_pcl_integration("gmail")
    assert integration["sync_cursor"]["last_timestamp_ms"] == 1700000100000
    assert integration["sync_cursor"]["last_item_count"] == 0
    assert len(database.get_feed_items_last_n_days(3650, source="gmail")) == 2
    assert database.get_feature_signal("local_user", "gmail", "label-work")["usage_count"] == 1


def test_calendar_and_notion_sync_import_metadata(monkeypatch, tmp_path):
    import database

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'integration_jobs_metadata.db')
    database.create_tables()
    database.connect_pcl_integration(
        source="calendar",
        name="Calendar",
        scopes=["event_metadata"],
        metadata={
            "events": [
                {
                    "title": "YC interview prep",
                    "project": "PersonaLayer",
                    "attendees": ["Alex", "Maya"],
                    "start": "2026-05-11T10:00:00Z",
                    "duration_minutes": 60,
                    "attendee_count": 5,
                }
            ]
        },
    )
    database.connect_pcl_integration(
        source="notion",
        name="Notion",
        scopes=["page_activity"],
        metadata={
            "pages": [
                {
                    "title": "Roadmap notes",
                    "workspace": "Product",
                    "object_type": "project",
                    "tags": ["Roadmap"],
                    "last_edited_time": "2026-05-11T12:00:00Z",
                }
            ]
        },
    )

    from pcl.integration_jobs import sync_integration
    calendar = sync_integration("calendar")
    notion = sync_integration("notion")

    assert calendar["status"] == "ok"
    assert notion["status"] == "ok"
    assert len(database.get_feed_items_last_n_days(3650, source="calendar")) == 1
    assert len(database.get_feed_items_last_n_days(3650, source="notion")) == 1
    signal_names = {signal["name"] for signal in database.get_persona_signals_last_n_days(3650)}
    assert "long_meetings" in signal_names
    assert "notion_tag:roadmap" in signal_names
    assert database.get_feature_signal("local_user", "calendar", "long-meeting")["usage_count"] == 1
    assert database.get_feature_signal("local_user", "calendar", "group-meeting")["usage_count"] == 1
    assert database.get_feature_signal("local_user", "notion", "tag-roadmap")["usage_count"] == 1
    from pcl.memory import read_memory_file
    assert "Calendar event observed: YC interview prep." in read_memory_file("local_user", "daily-log")["content"]
    assert "Alex appears in calendar meetings." in read_memory_file("local_user", "people")["content"]
    assert "notion file/note touched: Roadmap notes." in read_memory_file("local_user", "projects")["content"]
    assert "notion knowledge tag/topic: roadmap." in read_memory_file("local_user", "scratchpad")["content"]


def test_import_job_requires_metadata_payload(monkeypatch, tmp_path):
    import database

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'integration_jobs_missing_payload.db')
    database.create_tables()
    database.connect_pcl_integration(
        source="gmail",
        name="Gmail",
        scopes=["email_metadata"],
        metadata={"account_hint": "user"},
    )

    from pcl.integration_jobs import sync_integration
    result = sync_integration("gmail")

    assert result["status"] == "error"
    assert result["error"] == "import_metadata_required"
    assert database.get_pcl_integration("gmail")["last_sync_status"] == "error"


def test_daily_refresh_connector_step_syncs_connected_integrations(monkeypatch, tmp_path):
    import database

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'integration_jobs_daily.db')
    database.create_tables()
    database.connect_pcl_integration(
        source="gmail",
        name="Gmail",
        scopes=["email_metadata"],
        metadata={
            "user_id": "user_1",
            "messages": [
                {
                    "labels": ["Focus"],
                    "thread_size": 1,
                    "timestamp": 1700000000000,
                }
            ],
        },
        user_id="user_1",
    )

    from pcl.daily_refresh import connector_sync
    result = connector_sync("user_1")

    assert result["synced"] == 1
    assert result["items_synced"] == 1
    assert database.get_feature_signal("user_1", "gmail", "label-focus")["usage_count"] == 1


def test_spotify_youtube_and_apple_health_sync_metadata_to_v1_events(monkeypatch, tmp_path):
    import database

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'integration_jobs_more_connectors.db')
    database.create_tables()
    database.connect_pcl_integration(
        source="spotify",
        name="Spotify",
        scopes=["recently_played"],
        metadata={
            "recently_played": [
                {
                    "played_at": "2026-05-11T08:00:00Z",
                    "duration_minutes": 45,
                    "genres": ["Focus", "Ambient"],
                }
            ]
        },
    )
    database.connect_pcl_integration(
        source="youtube",
        name="YouTube",
        scopes=["watch_metadata"],
        metadata={
            "watch_history": [
                {
                    "watched_at": "2026-05-11T20:00:00Z",
                    "category": "AI Tutorial",
                    "duration_minutes": 25,
                }
            ]
        },
    )
    database.connect_pcl_integration(
        source="apple_health",
        name="Apple Health",
        scopes=["activity_metadata"],
        metadata={
            "activity": [
                {
                    "date": "2026-05-11T06:00:00Z",
                    "active_minutes": 42,
                    "stand_hours": 9,
                    "sleep_hours": 7.5,
                }
            ]
        },
    )

    from pcl.integration_jobs import sync_integration
    spotify = sync_integration("spotify")
    youtube = sync_integration("youtube")
    health = sync_integration("apple_health")

    assert spotify["status"] == "ok"
    assert youtube["status"] == "ok"
    assert health["status"] == "ok"
    assert database.get_feature_signal("local_user", "spotify", "long-focus-session")["usage_count"] == 1
    assert database.get_feature_signal("local_user", "youtube", "category-ai-tutorial")["usage_count"] == 1
    assert database.get_feature_signal("local_user", "apple-health", "active-day")["usage_count"] == 1


def test_new_provider_syncs_import_metadata_to_v1_events(monkeypatch, tmp_path):
    import database

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'integration_jobs_new_providers.db')
    database.create_tables()
    database.connect_pcl_integration(
        source="google_drive",
        name="Google Drive",
        scopes=["file_metadata"],
        metadata={
            "files": [{
                "name": "PersonaLayer Notes",
                "mime_type": "application/vnd.google-apps.document",
                "folder": "Product",
                "last_edited_time": "2026-05-11T12:30:00Z",
            }]
        },
    )
    database.connect_pcl_integration(
        source="instagram",
        name="Instagram",
        scopes=["feed_activity"],
        metadata={
            "items": [{
                "content_type": "reel",
                "topic": "Productivity",
                "engagement": "watched",
                "timestamp": 1700000000000,
            }]
        },
    )
    database.connect_pcl_integration(
        source="chatgpt",
        name="ChatGPT",
        scopes=["session_signals"],
        metadata={
            "sessions": [{
                "task_type": "Writing",
                "model": "gpt-4",
                "timestamp": 1700000000000,
            }]
        },
    )
    database.connect_pcl_integration(
        source="vscode",
        name="VS Code",
        scopes=["project_activity"],
        metadata={
            "sessions": [{
                "project": "Personalayer",
                "language": "Python",
                "task_type": "Refactor",
                "active_minutes": 40,
                "timestamp": 1700000000000,
            }]
        },
    )
    database.connect_pcl_integration(
        source="terminal",
        name="Terminal",
        scopes=["command_metadata"],
        metadata={
            "commands": [{
                "project": "Personalayer",
                "command_category": "Test",
                "shell": "powershell",
                "timestamp": 1700000000000,
            }]
        },
    )

    from pcl.integration_jobs import sync_integration
    results = {
        source: sync_integration(source)
        for source in ["google_drive", "instagram", "chatgpt", "vscode", "terminal"]
    }

    assert {result["status"] for result in results.values()} == {"ok"}
    assert database.get_feature_signal("local_user", "google-drive", "document-activity")["usage_count"] == 1
    assert database.get_feature_signal("local_user", "instagram", "topic-productivity")["usage_count"] == 1
    assert database.get_feature_signal("local_user", "chatgpt", "task-writing")["usage_count"] == 1
    assert database.get_feature_signal("local_user", "vscode", "language-python")["usage_count"] == 1
    assert database.get_feature_signal("local_user", "terminal", "command-test")["usage_count"] == 1
    from pcl.memory import read_memory_file
    assert "google_drive file/note touched: PersonaLayer Notes." in read_memory_file("local_user", "projects")["content"]
    assert "google_drive document type used: document." in read_memory_file("local_user", "preferences")["content"]
