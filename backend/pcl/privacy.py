import re
from typing import Any


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)")
TOKEN_RE = re.compile(r"\b(?:sk|pk|ghp|gho|xoxb|xoxp|ya29)[-_A-Za-z0-9]{12,}\b")
CREDIT_CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
UUID_RE = re.compile(r"^[a-f0-9]{8}-[a-f0-9]{4}-[1-5][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$", re.IGNORECASE)
SECRET_KEY_PARTS = (
    "access_token",
    "refresh_token",
    "id_token",
    "client_secret",
    "authorization",
    "password",
    "secret",
    "token",
    "cookie",
    "credential",
    "api_key",
    "private_key",
    "passphrase",
    "pin",
    "ssn",
    "social_security",
)
SAFE_TOKEN_METADATA_KEYS = {
    "tokens",
    "token_prefix",
    "has_refresh_token",
    "push_token_id",
}


def contains_blocked_secret(value: Any) -> bool:
    """Return True for credentials/payment secrets that should not enter the local vault."""
    if isinstance(value, str):
        return bool(TOKEN_RE.search(value) or CREDIT_CARD_RE.search(value))
    if isinstance(value, list) or isinstance(value, tuple):
        return any(contains_blocked_secret(item) for item in value)
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower()
            if any(part in normalized for part in SECRET_KEY_PARTS):
                return True
            if contains_blocked_secret(item):
                return True
    return False


def egress_filter(value: Any) -> Any:
    """Filter data as it leaves PersonaLayer for agents, apps, SDKs, or cloud."""
    return _drop_secret_keys(scrub_pii(value))


def scrub_pii(value: Any) -> Any:
    if isinstance(value, str):
        if UUID_RE.fullmatch(value):
            return value
        scrubbed = TOKEN_RE.sub("[token]", value)
        scrubbed = EMAIL_RE.sub("[email]", scrubbed)
        scrubbed = PHONE_RE.sub("[phone]", scrubbed)
        scrubbed = CREDIT_CARD_RE.sub("[card]", scrubbed)
        return scrubbed
    if isinstance(value, list):
        return [scrub_pii(item) for item in value]
    if isinstance(value, tuple):
        return tuple(scrub_pii(item) for item in value)
    if isinstance(value, dict):
        return {key: scrub_pii(item) for key, item in value.items()}
    return value


def strip_raw_content(signal: dict) -> dict:
    allowed = {
        "source",
        "signal_type",
        "name",
        "weight",
        "confidence",
        "timestamp",
        "feature_id",
        "feature_name",
        "event_type",
    }
    filtered = {key: value for key, value in signal.items() if key in allowed}
    return scrub_pii(filtered)


def sanitize_integration_metadata(metadata: Any) -> dict:
    if not isinstance(metadata, dict):
        return {}
    return _drop_secret_keys(metadata)


def _drop_secret_keys(value: Any) -> Any:
    if isinstance(value, list):
        return [_drop_secret_keys(item) for item in value]
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            normalized = str(key).lower()
            if normalized not in SAFE_TOKEN_METADATA_KEYS and any(part in normalized for part in SECRET_KEY_PARTS):
                continue
            clean[key] = _drop_secret_keys(item)
        return clean
    return value
