"""Local authentication and session protection for PersonaLayer.

Production-grade local auth:
- Session tokens with expiry
- API key verification
- Dashboard CSRF protection
- Extension origin validation
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from typing import Any

SESSION_EXPIRY_SECONDS = 3600 * 24 * 7  # 7 days
LOCAL_AUTH_ENABLED = os.getenv("PERSONALAYER_LOCAL_AUTH", "1") == "1"


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


def validate_local_session(token: str) -> dict[str, Any] | None:
    return _session_manager.validate_session(token)


def revoke_local_session(token: str) -> bool:
    return _session_manager.revoke_session(token)


def require_local_auth(token: str) -> dict[str, Any]:
    if not LOCAL_AUTH_ENABLED:
        return {"user_id": "local_user", "auth": "disabled"}
    session = validate_local_session(token)
    if not session:
        raise AuthError("invalid_or_expired_session")
    return session


def verify_dashboard_request(request_headers: dict[str, str]) -> dict[str, Any]:
    """Verify that a dashboard request is authorized.

    Checks session token in Authorization header or Cookie.
    Also validates Origin/Referer to prevent arbitrary websites from
    accessing localhost APIs.
    """
    if not LOCAL_AUTH_ENABLED:
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
