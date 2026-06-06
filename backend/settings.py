import json
import os
from pathlib import Path
from typing import Any


SETTINGS_FILE = Path.home() / ".personalayer" / "settings.json"
DEFAULT_MAX_REQUEST_BYTES = 1024 * 1024


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


def csv_env(name: str) -> set[str]:
    raw = os.getenv(name, "")
    return {item.strip().rstrip("/") for item in raw.split(",") if item.strip()}


def is_production_env() -> bool:
    return os.getenv("PERSONALAYER_ENV", "").strip().lower() in {"prod", "production"}


def max_request_bytes() -> int:
    raw = os.getenv("PERSONALAYER_MAX_REQUEST_BYTES", "").strip()
    if not raw:
        return DEFAULT_MAX_REQUEST_BYTES
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_REQUEST_BYTES
    return max(16 * 1024, min(value, 10 * 1024 * 1024))


def validate_production_config() -> None:
    """Fail fast for settings that would make an exposed backend unsafe."""
    if not is_production_env():
        return

    errors: list[str] = []
    if os.getenv("PERSONALAYER_LOCAL_AUTH", "1") != "1":
        errors.append("PERSONALAYER_LOCAL_AUTH must be 1 in production")
    if not os.getenv("PERSONALAYER_LOCAL_AUTH_BOOTSTRAP_TOKEN", "").strip():
        errors.append("PERSONALAYER_LOCAL_AUTH_BOOTSTRAP_TOKEN must be set in production")
    if os.getenv("PERSONALAYER_DEV_MODE", "0") == "1":
        errors.append("PERSONALAYER_DEV_MODE must not be 1 in production")

    origins = csv_env("PERSONALAYER_ALLOWED_ORIGINS")
    if not origins:
        errors.append("PERSONALAYER_ALLOWED_ORIGINS must be set in production")
    if "*" in origins:
        errors.append("PERSONALAYER_ALLOWED_ORIGINS must not contain *")
    for origin in origins:
        if origin.startswith("http://") and "localhost" not in origin and "127.0.0.1" not in origin:
            errors.append(f"non-local origin must use https: {origin}")

    extension_origins = csv_env("PERSONALAYER_EXTENSION_ORIGINS")
    if "*" in extension_origins:
        errors.append("PERSONALAYER_EXTENSION_ORIGINS must not contain *")

    if errors:
        raise RuntimeError("Unsafe PersonaLayer production configuration: " + "; ".join(errors))
