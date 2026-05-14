"""Unit tests for connector clients and privacy filter."""
import pytest
from datetime import datetime, timezone

# These tests don't require external APIs - they test logic and filters

class TestConnectorPrivacyFilter:
    def test_gmail_field_whitelist(self):
        from backend.pcl.connectors import ConnectorPrivacyFilter
        raw = {
            "id": "msg123",
            "threadId": "thread456",
            "labelIds": ["INBOX", "UNREAD"],
            "snippet": "Hello world",
            "payload": {"headers": [{"name": "From", "value": "test@example.com"}]},
            "internalDate": "1234567890000",
            "password": "secret123",  # should be stripped
            "secretKey": "abc",       # should be stripped
        }
        filtered = ConnectorPrivacyFilter.filter_event("gmail", raw)
        assert filtered["id"] == "msg123"
        assert filtered["threadId"] == "thread456"
        assert "labelIds" in filtered
        assert "password" not in filtered
        assert "secretKey" not in filtered
        assert "payload" not in filtered  # not in whitelist

    def test_blocked_keywords_detected(self):
        from backend.pcl.connectors import ConnectorPrivacyFilter
        assert ConnectorPrivacyFilter.has_blocked_keywords({"text": "my password is 123"})
        assert ConnectorPrivacyFilter.has_blocked_keywords({"data": "ssn: 123-45-6789"})
        assert not ConnectorPrivacyFilter.has_blocked_keywords({"text": "hello world"})

    def test_spotify_field_whitelist(self):
        from backend.pcl.connectors import ConnectorPrivacyFilter
        raw = {
            "track": {"name": "Song", "id": "track123"},
            "played_at": "2024-01-01T00:00:00Z",
            "context": {"type": "playlist"},
            "password": "secret",  # stripped
        }
        filtered = ConnectorPrivacyFilter.filter_event("spotify", raw)
        assert "track" in filtered
        assert "password" not in filtered

    def test_unknown_connector_passes_through_with_keyword_filter(self):
        from backend.pcl.connectors import ConnectorPrivacyFilter
        raw = {"name": "Test", "value": 42}
        filtered = ConnectorPrivacyFilter.filter_event("unknown", raw)
        assert filtered == raw


class TestConnectorCursorStore:
    def test_cursor_serialization(self):
        from backend.pcl.connectors import ConnectorCursorStore
        store = ConnectorCursorStore("memory")
        store.save_cursor("gmail", "after:12345")
        assert store.load_cursor("gmail") == "after:12345"
        assert store.load_cursor("spotify") is None

    def test_spotify_after_cursor(self):
        from backend.pcl.connectors import ConnectorCursorStore
        store = ConnectorCursorStore("memory")
        store.save_cursor("spotify", "1700000000000")
        cursor = store.load_cursor("spotify")
        assert cursor == "1700000000000"


class TestConnectorError:
    def test_typed_errors(self):
        from backend.pcl.connectors import ConnectorError
        err = ConnectorError.rate_limited(retry_after=30)
        assert "30" in str(err)
        err2 = ConnectorError.api_error(404, "Not found")
        assert "404" in str(err2)
