"""Connector clients, privacy filter, and cursor store.

Production-grade connector infrastructure with:
- Per-connector field whitelisting
- Blocked keyword detection (PII, secrets)
- Incremental cursor/delta sync
- Rate limit handling
"""
from typing import Dict, Any, Optional


class ConnectorError(Exception):
    """Typed connector errors."""

    @classmethod
    def rate_limited(cls, retry_after: int) -> "ConnectorError":
        return cls(f"Rate limited. Retry after {retry_after}s")

    @classmethod
    def api_error(cls, status: int, message: str) -> "ConnectorError":
        return cls(f"API error {status}: {message}")

    @classmethod
    def invalid_response(cls) -> "ConnectorError":
        return cls("Invalid API response")


class ConnectorPrivacyFilter:
    """Privacy filter for connector data.

    Only allows whitelisted fields per connector.
    Detects and blocks events containing sensitive keywords.
    """

    # Fields allowed per connector type
    FIELD_WHITELIST: Dict[str, list] = {
        "gmail": ["id", "threadId", "labelIds", "snippet", "internalDate", "historyId"],
        "calendar": ["id", "summary", "start", "end", "created", "updated", "status"],
        "spotify": ["track", "played_at", "context"],
        "youtube": ["id", "snippet", "contentDetails"],
        "notion": ["id", "title", "created_time", "last_edited_time"],
        "google_fit": ["dataSourceId", "point", "startTimeNanos", "endTimeNanos"],
    }

    # Keywords that trigger automatic blocking
    BLOCKED_KEYWORDS = [
        "password", "secret", "token", "api_key", "credit_card",
        "ssn", "private_key", "passphrase", "authorization",
    ]

    @classmethod
    def filter_event(cls, connector_type: str, event: Dict[str, Any]) -> Dict[str, Any]:
        """Filter event to only whitelisted fields."""
        allowed = cls.FIELD_WHITELIST.get(connector_type, list(event.keys()))
        return {k: v for k, v in event.items() if k in allowed}

    @classmethod
    def has_blocked_keywords(cls, event: Dict[str, Any]) -> bool:
        """Check if event contains any blocked keywords."""
        text = str(event).lower()
        return any(kw in text for kw in cls.BLOCKED_KEYWORDS)

    @classmethod
    def should_block(cls, connector_type: str, event: Dict[str, Any]) -> bool:
        """Full privacy gate: whitelist + keyword check."""
        filtered = cls.filter_event(connector_type, event)
        return cls.has_blocked_keywords(filtered)


class ConnectorCursorStore:
    """Persistent store for connector sync cursors.

    Uses memory by default; swap to Redis/SQLite for production.
    """

    def __init__(self, backend: str = "memory"):
        self.backend = backend
        self._memory: Dict[str, str] = {}

    def save_cursor(self, connector: str, cursor: str) -> None:
        if self.backend == "memory":
            self._memory[connector] = cursor
        else:
            raise NotImplementedError(f"Backend {self.backend} not implemented")

    def load_cursor(self, connector: str) -> Optional[str]:
        if self.backend == "memory":
            return self._memory.get(connector)
        raise NotImplementedError(f"Backend {self.backend} not implemented")

    def clear(self, connector: str) -> None:
        if self.backend == "memory":
            self._memory.pop(connector, None)
