from dataclasses import dataclass, field
from typing import Literal, Protocol


CollectorMode = Literal["push", "poll", "watch", "proxy", "manual"]


@dataclass(frozen=True)
class CollectorPermission:
    name: str
    description: str
    required: bool = True


@dataclass(frozen=True)
class CollectorSpec:
    source: str
    display_name: str
    event_types: tuple[str, ...]
    mode: CollectorMode
    permissions: tuple[CollectorPermission, ...] = field(default_factory=tuple)
    raw_content_stored: bool = False
    enabled_by_default: bool = False


class Collector(Protocol):
    spec: CollectorSpec

    def start(self) -> None:
        """Start the collector if it has a resident runtime."""


def builtin_collector_specs() -> list[CollectorSpec]:
    return [
        CollectorSpec(
            source="browser_extension",
            display_name="Browser extension",
            event_types=("browser_activity",),
            mode="push",
            permissions=(
                CollectorPermission("tabs", "Read active tab URL, title, and timing."),
                CollectorPermission("localhost", "Send events to the local daemon."),
            ),
            raw_content_stored=False,
            enabled_by_default=True,
        ),
        CollectorSpec(
            source="claude_code",
            display_name="Claude Code watcher",
            event_types=("session_signals",),
            mode="watch",
            permissions=(
                CollectorPermission("filesystem", "Read Claude Code JSONL session files locally."),
            ),
            raw_content_stored=False,
            enabled_by_default=True,
        ),
        CollectorSpec(
            source="shell",
            display_name="Shell LLM wrappers",
            event_types=("prompt",),
            mode="manual",
            permissions=(
                CollectorPermission("shell_rc", "Install shell wrappers in user shell profile.", required=False),
            ),
            raw_content_stored=True,
            enabled_by_default=False,
        ),
        CollectorSpec(
            source="llm",
            display_name="Generic LLM CLI wrapper",
            event_types=("prompt", "session_signals"),
            mode="manual",
            permissions=(
                CollectorPermission("shell_rc", "Install local wrappers for generic LLM CLI prompts.", required=False),
            ),
            raw_content_stored=True,
            enabled_by_default=False,
        ),
        CollectorSpec(
            source="gmail",
            display_name="Gmail metadata import",
            event_types=("email_metadata",),
            mode="manual",
            permissions=(
                CollectorPermission("gmail_metadata", "Import labels, timing, sender domains, and thread metadata."),
            ),
            raw_content_stored=False,
            enabled_by_default=False,
        ),
        CollectorSpec(
            source="calendar",
            display_name="Calendar metadata import",
            event_types=("event_metadata",),
            mode="manual",
            permissions=(
                CollectorPermission("calendar_metadata", "Import event timing, duration, status, and attendee counts."),
            ),
            raw_content_stored=False,
            enabled_by_default=False,
        ),
        CollectorSpec(
            source="notion",
            display_name="Notion activity import",
            event_types=("page_activity",),
            mode="manual",
            permissions=(
                CollectorPermission("notion_metadata", "Import workspace, page type, tag, and edit timing metadata."),
            ),
            raw_content_stored=False,
            enabled_by_default=False,
        ),
        CollectorSpec(
            source="github",
            display_name="GitHub sync",
            event_types=("commit", "star", "issue", "pr_review", "fork"),
            mode="poll",
            permissions=(
                CollectorPermission("network", "Fetch public GitHub profile activity."),
                CollectorPermission("github_token", "Use GITHUB_TOKEN for higher API limits.", required=False),
            ),
            raw_content_stored=True,
            enabled_by_default=False,
        ),
        CollectorSpec(
            source="google_drive",
            display_name="Google Drive metadata import",
            event_types=("file_activity", "folder_activity"),
            mode="manual",
            permissions=(
                CollectorPermission("drive_metadata", "Import file type, folder, ownership, and edit timing metadata."),
            ),
            raw_content_stored=False,
            enabled_by_default=False,
        ),
        CollectorSpec(
            source="youtube",
            display_name="YouTube watch metadata import",
            event_types=("watch_metadata", "category_patterns"),
            mode="manual",
            permissions=(
                CollectorPermission("youtube_metadata", "Import watch category, session timing, and duration metadata."),
            ),
            raw_content_stored=False,
            enabled_by_default=False,
        ),
        CollectorSpec(
            source="spotify",
            display_name="Spotify listening metadata import",
            event_types=("recently_played", "session_timing", "genre_patterns"),
            mode="manual",
            permissions=(
                CollectorPermission("spotify_metadata", "Import recently played timing, genre, and session metadata."),
            ),
            raw_content_stored=False,
            enabled_by_default=False,
        ),
        CollectorSpec(
            source="apple_health",
            display_name="Apple Health metadata import",
            event_types=("activity_metadata", "sleep_timing", "workout_patterns"),
            mode="manual",
            permissions=(
                CollectorPermission("health_metadata", "Import activity, sleep, and workout summary metadata."),
            ),
            raw_content_stored=False,
            enabled_by_default=False,
        ),
        CollectorSpec(
            source="linkedin",
            display_name="LinkedIn activity bridge",
            event_types=("feed_activity", "profile_activity", "post_activity"),
            mode="push",
            permissions=(
                CollectorPermission("extension_bridge", "Capture local LinkedIn activity through the browser extension."),
            ),
            raw_content_stored=True,
            enabled_by_default=False,
        ),
        CollectorSpec(
            source="x",
            display_name="X activity bridge",
            event_types=("feed_activity", "post_activity", "topic_activity"),
            mode="push",
            permissions=(
                CollectorPermission("extension_bridge", "Capture local X activity through the browser extension."),
            ),
            raw_content_stored=True,
            enabled_by_default=False,
        ),
        CollectorSpec(
            source="instagram",
            display_name="Instagram activity bridge",
            event_types=("feed_activity", "creator_activity", "topic_activity"),
            mode="push",
            permissions=(
                CollectorPermission("extension_bridge", "Capture local Instagram activity through the browser extension."),
            ),
            raw_content_stored=True,
            enabled_by_default=False,
        ),
        CollectorSpec(
            source="chatgpt",
            display_name="ChatGPT activity bridge",
            event_types=("prompt", "session_signals"),
            mode="push",
            permissions=(
                CollectorPermission("extension_bridge", "Capture local ChatGPT session signals through the browser extension."),
            ),
            raw_content_stored=True,
            enabled_by_default=False,
        ),
        CollectorSpec(
            source="claude",
            display_name="Claude activity bridge",
            event_types=("prompt", "session_signals"),
            mode="push",
            permissions=(
                CollectorPermission("extension_bridge", "Capture local Claude session signals through the browser extension."),
            ),
            raw_content_stored=True,
            enabled_by_default=False,
        ),
        CollectorSpec(
            source="perplexity",
            display_name="Perplexity activity bridge",
            event_types=("query", "session_signals"),
            mode="push",
            permissions=(
                CollectorPermission("extension_bridge", "Capture local Perplexity query signals through the browser extension."),
            ),
            raw_content_stored=True,
            enabled_by_default=False,
        ),
        CollectorSpec(
            source="opencode",
            display_name="OpenCode activity bridge",
            event_types=("coding_session", "prompt"),
            mode="push",
            permissions=(
                CollectorPermission("extension_bridge", "Capture local OpenCode session signals."),
            ),
            raw_content_stored=True,
            enabled_by_default=False,
        ),
        CollectorSpec(
            source="cursor",
            display_name="Cursor activity bridge",
            event_types=("coding_session", "prompt", "project_activity"),
            mode="manual",
            permissions=(
                CollectorPermission("ide_metadata", "Import project and assistant-session metadata from Cursor."),
            ),
            raw_content_stored=True,
            enabled_by_default=False,
        ),
        CollectorSpec(
            source="gemini",
            display_name="Gemini activity bridge",
            event_types=("prompt", "session_signals"),
            mode="push",
            permissions=(
                CollectorPermission("extension_bridge", "Capture local Gemini session signals through the browser extension."),
            ),
            raw_content_stored=True,
            enabled_by_default=False,
        ),
        CollectorSpec(
            source="grok",
            display_name="Grok activity bridge",
            event_types=("prompt", "session_signals"),
            mode="push",
            permissions=(
                CollectorPermission("extension_bridge", "Capture local Grok session signals through the browser extension."),
            ),
            raw_content_stored=True,
            enabled_by_default=False,
        ),
        CollectorSpec(
            source="github_copilot",
            display_name="GitHub Copilot activity bridge",
            event_types=("coding_session", "completion_activity"),
            mode="manual",
            permissions=(
                CollectorPermission("ide_metadata", "Import local Copilot usage and project metadata."),
            ),
            raw_content_stored=False,
            enabled_by_default=False,
        ),
        CollectorSpec(
            source="aider",
            display_name="Aider activity bridge",
            event_types=("coding_session", "prompt"),
            mode="manual",
            permissions=(
                CollectorPermission("local_logs", "Import local Aider session metadata."),
            ),
            raw_content_stored=True,
            enabled_by_default=False,
        ),
        CollectorSpec(
            source="terminal",
            display_name="Terminal activity bridge",
            event_types=("command_metadata", "project_activity"),
            mode="manual",
            permissions=(
                CollectorPermission("shell_rc", "Install local wrappers for terminal command metadata.", required=False),
            ),
            raw_content_stored=False,
            enabled_by_default=False,
        ),
        CollectorSpec(
            source="vscode",
            display_name="VS Code activity bridge",
            event_types=("project_activity", "extension_activity"),
            mode="manual",
            permissions=(
                CollectorPermission("ide_metadata", "Import local VS Code project and extension metadata."),
            ),
            raw_content_stored=False,
            enabled_by_default=False,
        ),
        CollectorSpec(
            source="ide",
            display_name="IDE activity bridge",
            event_types=("project_activity", "coding_session"),
            mode="manual",
            permissions=(
                CollectorPermission("ide_metadata", "Import generic local IDE project activity metadata."),
            ),
            raw_content_stored=False,
            enabled_by_default=False,
        ),
    ]
