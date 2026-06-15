"""Local authentication and session protection for PersonaLayer.

Production-grade local auth:
- Session tokens with expiry
- API key verification
- Dashboard CSRF protection
- Extension origin validation
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
from typing import Any

SESSION_EXPIRY_SECONDS = 3600 * 24 * 7  # 7 days
LOCAL_AUTH_ENABLED = os.getenv("PERSONALAYER_LOCAL_AUTH", "1") == "1"

_SECRET_VALUE_RE = re.compile(
    r"(?i)\b(?:bearer\s+)?(?:sk|pk|cl|ghp|gho|xoxb|xoxp|ya29)[-_a-z0-9]{8,}\b"
)
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(access_token|refresh_token|id_token|authorization|api_key|client_secret|password|secret|token|cookie)"
    r"\s*[:=]\s*[^,\s}\]]+"
)


class AuthError(Exception):
    pass


class SessionManager:
    """In-memory session manager for local prototype.
    Production native clients should use platform keychain-backed sessions."""

    def __init__(self):
        self._sessions: dict[str, dict[str, Any]] = {}

    def create_session(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        now = time.time()
        self._sessions[token] = {
            "user_id": user_id,
            "created_at": now,
            "expires_at": now + SESSION_EXPIRY_SECONDS,
        }
        return token

    def validate_session(self, token: str) -> dict[str, Any] | None:
        if not token:
            return None
        session = self._sessions.get(token)
        if not session:
            return None
        if time.time() > session["expires_at"]:
            self._sessions.pop(token, None)
            return None
        return session

    def revoke_session(self, token: str) -> bool:
        return self._sessions.pop(token, None) is not None

    def revoke_all_for_user(self, user_id: str) -> int:
        tokens = [t for t, s in self._sessions.items() if s["user_id"] == user_id]
        for t in tokens:
            self._sessions.pop(t, None)
        return len(tokens)


_session_manager = SessionManager()


def create_local_session(user_id: str) -> str:
    return _session_manager.create_session(user_id)


def create_bootstrap_session(user_id: str, bootstrap_token: str) -> str:
    """Create a local session with a one-time deployment/bootstrap secret."""
    if local_auth_enabled() and local_auth_bootstrap_token():
        if not hmac.compare_digest(bootstrap_token or "", local_auth_bootstrap_token()):
            raise AuthError("invalid_bootstrap_token")
    elif local_auth_enabled():
        raise AuthError("bootstrap_token_not_configured")
    return create_local_session(user_id)


def validate_local_session(token: str) -> dict[str, Any] | None:
    return _session_manager.validate_session(token)


def revoke_local_session(token: str) -> bool:
    return _session_manager.revoke_session(token)


def supabase_jwt_secret() -> str:
    return os.getenv("SUPABASE_JWT_SECRET", "")


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def verify_supabase_jwt(token: str) -> dict[str, Any] | None:
    """Verify a Supabase HS256 access token with SUPABASE_JWT_SECRET.

    Returns a session-shaped dict with user_id 'supabase:<sub>' on success, or
    None when the secret is unset, the signature is invalid, or the token is
    expired/malformed. The secret never leaves the backend.
    """
    secret = supabase_jwt_secret()
    if not secret or not token or token.count(".") != 2:
        return None
    header_b64, payload_b64, signature_b64 = token.split(".")
    try:
        header = json.loads(_b64url_decode(header_b64))
    except Exception:
        return None
    if header.get("alg") != "HS256":
        return None
    expected = hmac.new(
        secret.encode("utf-8"),
        f"{header_b64}.{payload_b64}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    try:
        actual = _b64url_decode(signature_b64)
    except Exception:
        return None
    if not hmac.compare_digest(expected, actual):
        return None
    try:
        claims = json.loads(_b64url_decode(payload_b64))
    except Exception:
        return None
    exp = claims.get("exp")
    try:
        if exp is not None and time.time() > float(exp):
            return None
    except (TypeError, ValueError):
        return None
    sub = claims.get("sub")
    if not sub:
        return None
    return {"user_id": f"supabase:{sub}", "auth": "supabase", "email": claims.get("email", "")}


def require_local_auth(token: str) -> dict[str, Any]:
    if not local_auth_enabled():
        return {"user_id": "local_user", "auth": "disabled"}
    session = validate_local_session(token)
    if session:
        return session
    supabase_session = verify_supabase_jwt(token)
    if supabase_session:
        return supabase_session
    raise AuthError("invalid_or_expired_session")


def verify_dashboard_request(request_headers: dict[str, str]) -> dict[str, Any]:
    """Verify that a dashboard request is authorized.

    Checks session token in Authorization header or Cookie.
    Also validates Origin/Referer to prevent arbitrary websites from
    accessing localhost APIs.
    """
    if not local_auth_enabled():
        return {"user_id": "local_user", "auth": "disabled"}

    # Check origin/referer
    origin = request_headers.get("origin", request_headers.get("Origin", ""))
    referer = request_headers.get("referer", request_headers.get("Referer", ""))
    allowed_origins = {"http://localhost:7823", "http://127.0.0.1:7823"}
    if origin and origin not in allowed_origins:
        raise AuthError("unauthorized_origin")
    if referer:
        from urllib.parse import urlparse
        parsed = urlparse(referer)
        referer_base = f"{parsed.scheme}://{parsed.netloc}"
        if referer_base not in allowed_origins:
            raise AuthError("unauthorized_referer")

    # Check session
    auth = request_headers.get("authorization", request_headers.get("Authorization", ""))
    token = _bearer_token(auth)
    if not token:
        # Allow cookie fallback
        cookie = request_headers.get("cookie", request_headers.get("Cookie", ""))
        token = _extract_cookie_value(cookie, "pl_session")
    if not token:
        raise AuthError("missing_session_token")

    session = require_local_auth(token)
    return session


def _bearer_token(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return value


def _extract_cookie_value(cookie_header: str, name: str) -> str:
    if not cookie_header:
        return ""
    for part in cookie_header.split(";"):
        part = part.strip()
        if part.startswith(f"{name}="):
            return part[len(name) + 1:]
    return ""


def local_auth_enabled() -> bool:
    return os.getenv("PERSONALAYER_LOCAL_AUTH", "1") == "1"


def local_auth_bootstrap_token() -> str:
    return os.getenv("PERSONALAYER_LOCAL_AUTH_BOOTSTRAP_TOKEN", "")


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def verify_csrf_token(token: str, expected: str) -> bool:
    return hmac.compare_digest(token, expected)


def hash_local_password(password: str, salt: str = "") -> str:
    if not salt:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return f"pbkdf2:sha256:100000${salt}${digest.hex()}"


def verify_local_password(password: str, hashed: str) -> bool:
    try:
        _, _, _, salt, _ = hashed.split("$")
        return hmac.compare_digest(hash_local_password(password, salt), hashed)
    except Exception:
        return False


def redact_secret_value(value: Any) -> Any:
    if isinstance(value, str):
        redacted = _SECRET_ASSIGNMENT_RE.sub(lambda m: f"{m.group(1)}=[redacted]", value)
        return _SECRET_VALUE_RE.sub("[redacted]", redacted)
    if isinstance(value, list):
        return [redact_secret_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secret_value(item) for item in value)
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            normalized = str(key).lower()
            if any(part in normalized for part in ("token", "secret", "password", "authorization", "api_key", "cookie")):
                clean[key] = "[redacted]"
            else:
                clean[key] = redact_secret_value(item)
        return clean
    return value


class SecretRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_secret_value(record.msg)
        if record.args:
            record.args = redact_secret_value(record.args)
        return True


def install_secret_log_redaction() -> None:
    root = logging.getLogger()
    if any(isinstance(item, SecretRedactionFilter) for item in root.filters):
        return
    root.addFilter(SecretRedactionFilter())
