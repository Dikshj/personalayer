from typing import Optional
from urllib.parse import parse_qs, urlparse

from core.events import BrowserActivityEvent, FeedActivityEvent, IngestionResult
from collectors.base import builtin_collector_specs
from database import insert_event, insert_feed_item
from living_persona import record_browsing_signals, record_feed_signals


SKIP_PATTERNS = ("localhost", "127.0.0.1", "chrome://", "chrome-extension://", "about:")

ALLOWED_FEED_SOURCES = {
    "x", "linkedin", "youtube", "google", "github",
    "chatgpt", "claude", "perplexity", "opencode",
    "cursor", "gemini", "grok", "github_copilot", "llm",
    "claude_code", "ollama", "aider", "sgpt",
    "shell", "terminal", "vscode", "ide",
}


def extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def extract_search_query(url: str) -> Optional[str]:
    try:
        params = parse_qs(urlparse(url).query)
        for key in ("q", "query", "search", "s", "k"):
            if key in params:
                return params[key][0]
    except Exception:
        pass
    return None


def should_skip_url(url: str) -> bool:
    return any(pattern in url for pattern in SKIP_PATTERNS)


class PersonaDaemon:
    """System-level ingestion core shared by HTTP, MCP, CLI, and collectors."""

    def status(self) -> dict:
        collectors = builtin_collector_specs()
        return {
            "status": "ok",
            "mode": "local_context_daemon",
            "bind": "127.0.0.1:7823",
            "storage": "local_sqlite",
            "raw_data_leaves_device": False,
            "interfaces": ["http", "mcp"],
            "collectors": [collector.source for collector in collectors],
            "collector_specs": [
                {
                    "source": collector.source,
                    "display_name": collector.display_name,
                    "event_types": list(collector.event_types),
                    "mode": collector.mode,
                    "permissions": [
                        {
                            "name": permission.name,
                            "description": permission.description,
                            "required": permission.required,
                        }
                        for permission in collector.permissions
                    ],
                    "raw_content_stored": collector.raw_content_stored,
                    "enabled_by_default": collector.enabled_by_default,
                }
                for collector in collectors
            ],
            "policy": {
                "scoped_context_contracts": True,
                "audit_log": True,
                "revocation": True,
            },
        }

    def ingest_browser_activity(self, event: BrowserActivityEvent) -> IngestionResult:
        if should_skip_url(event.url):
            return IngestionResult(status="skipped", source="browser", reason="local_or_internal_url")

        search_query = extract_search_query(event.url)
        insert_event(
            url=event.url,
            title=event.title or "",
            domain=extract_domain(event.url),
            time_spent_seconds=event.time_spent_seconds or 0,
            search_query=search_query,
            timestamp=event.timestamp,
        )
        record_browsing_signals(
            url=event.url,
            title=event.title or "",
            time_spent_seconds=event.time_spent_seconds or 0,
            search_query=search_query,
            timestamp=event.timestamp,
        )
        return IngestionResult(status="ok", source="browser")

    def ingest_feed_activity(self, event: FeedActivityEvent) -> IngestionResult:
        if event.source not in ALLOWED_FEED_SOURCES:
            return IngestionResult(status="error", source="feed", reason="unknown_source")
        if not event.content.strip():
            return IngestionResult(status="skipped", source="feed", reason="empty_content")

        content = event.content.strip()
        insert_feed_item(
            source=event.source,
            content_type=event.content_type,
            content=content,
            author=event.author or "",
            url=event.url or "",
            timestamp=event.timestamp,
        )
        record_feed_signals(
            source=event.source,
            content_type=event.content_type,
            content=content,
            author=event.author or "",
            url=event.url or "",
            timestamp=event.timestamp,
        )
        return IngestionResult(status="ok", source="feed")


daemon = PersonaDaemon()
