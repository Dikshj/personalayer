import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


def test_collector_enabled_uses_default_when_unconfigured(tmp_path, monkeypatch):
    from settings import is_collector_enabled

    monkeypatch.delenv("PERSONALAYER_ENABLED_COLLECTORS", raising=False)
    monkeypatch.delenv("PERSONALAYER_DISABLED_COLLECTORS", raising=False)

    assert is_collector_enabled("claude_code", True, tmp_path / "missing.json") is True
    assert is_collector_enabled("github", False, tmp_path / "missing.json") is False


def test_collector_enabled_reads_settings_file(tmp_path, monkeypatch):
    from settings import is_collector_enabled

    monkeypatch.delenv("PERSONALAYER_ENABLED_COLLECTORS", raising=False)
    monkeypatch.delenv("PERSONALAYER_DISABLED_COLLECTORS", raising=False)
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({
        "collectors": {
            "github": {"enabled": True},
            "claude_code": {"enabled": False},
        }
    }))

    assert is_collector_enabled("github", False, settings_file) is True
    assert is_collector_enabled("claude_code", True, settings_file) is False


def test_collector_enabled_env_allowlist_wins(tmp_path, monkeypatch):
    from settings import is_collector_enabled

    monkeypatch.setenv("PERSONALAYER_ENABLED_COLLECTORS", "github")

    assert is_collector_enabled("github", False, tmp_path / "missing.json") is True
    assert is_collector_enabled("claude_code", True, tmp_path / "missing.json") is False
