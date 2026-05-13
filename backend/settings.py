import json
import os
from pathlib import Path
from typing import Any


SETTINGS_FILE = Path.home() / ".personalayer" / "settings.json"


def load_settings(settings_file: Path = SETTINGS_FILE) -> dict[str, Any]:
    if not settings_file.exists():
        return {}
    try:
        data = json.loads(settings_file.read_text())
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def is_collector_enabled(
    source: str,
    default: bool,
    settings_file: Path = SETTINGS_FILE,
) -> bool:
    enabled_only = _csv_env("PERSONALAYER_ENABLED_COLLECTORS")
    if enabled_only is not None:
        return source in enabled_only

    disabled = _csv_env("PERSONALAYER_DISABLED_COLLECTORS") or set()
    if source in disabled:
        return False

    settings = load_settings(settings_file)
    collector_settings = settings.get("collectors", {})
    if isinstance(collector_settings, dict):
        configured = collector_settings.get(source, {})
        if isinstance(configured, dict) and "enabled" in configured:
            return bool(configured["enabled"])

    return default


def _csv_env(name: str) -> set[str] | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    return {item.strip() for item in raw.split(",") if item.strip()}
