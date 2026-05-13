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
            source="ollama",
            display_name="Ollama local proxy",
            event_types=("session_signals",),
            mode="proxy",
            permissions=(
                CollectorPermission("localhost_proxy", "Proxy local Ollama requests on 127.0.0.1."),
            ),
            raw_content_stored=False,
            enabled_by_default=False,
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
    ]
