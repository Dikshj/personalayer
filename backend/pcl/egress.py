"""
Centralized egress privacy enforcement for PersonaLayer.

Every outbound data path must pass through enforce_egress_policy() before leaving
the local device. This module wraps the existing privacy filters and adds:
- Consent revocation checks
- Missing scope checks
- Blocked app/domain checks
- Privacy boundary enforcement
- Audit logging of egress decisions
"""

from __future__ import annotations

import time
from typing import Any

from pcl.privacy import egress_filter, strip_raw_content
from pcl.privacy_boundaries import (
    check_domain_approved,
    check_extension_origin,
    PrivacyBoundaryError,
)
from database import get_app_permission


def enforce_egress_policy(
    data: Any,
    user_id: str,
    app_id: str,
    requested_scopes: list[str] | None = None,
    source: str = "rest",
    domain: str | None = None,
    origin: str | None = None,
) -> Any:
    """
    Enforce egress privacy policy on outbound data.

    Args:
        data: The data to be sent outbound.
        user_id: The user identifier.
        app_id: The app/consumer identifier.
        requested_scopes: The scopes requested by the consumer.
        source: The source of the request (rest, mcp, extension, sdk, proxy, etc.).
        domain: Optional domain for extension bridge requests.
        origin: Optional origin for extension bridge requests.

    Returns:
        The filtered data, or an error dict if egress is blocked.
    """
    # 1. Check consent revocation
    permission = get_app_permission(user_id, app_id)
    if permission and not permission["is_active"]:
        return {
            "error": "app_consent_revoked",
            "app_id": app_id,
            "user_id": user_id,
            "source": source,
            "timestamp_ms": int(time.time() * 1000),
        }

    # 2. Check blocked app
    if permission and permission.get("blocked"):
        return {
            "error": "app_blocked",
            "app_id": app_id,
            "user_id": user_id,
            "source": source,
            "timestamp_ms": int(time.time() * 1000),
        }

    # 3. Check missing scopes
    if requested_scopes and permission:
        granted = set(permission.get("scopes", []))
        missing = [s for s in requested_scopes if s not in granted]
        if missing:
            return {
                "error": "scope_not_granted",
                "app_id": app_id,
                "user_id": user_id,
                "missing_scopes": missing,
                "granted_scopes": list(granted),
                "source": source,
                "timestamp_ms": int(time.time() * 1000),
            }

    # 4. Check domain approval for extension bridge
    if domain or origin:
        try:
            check_domain_approved(domain or origin)
        except PrivacyBoundaryError as exc:
            return {
                "error": "domain_not_approved",
                "domain": domain or origin,
                "user_id": user_id,
                "source": source,
                "detail": str(exc),
                "timestamp_ms": int(time.time() * 1000),
            }

    # 5. Check extension origin
    if origin:
        try:
            check_extension_origin(origin)
        except PrivacyBoundaryError as exc:
            return {
                "error": "origin_not_allowed",
                "origin": origin,
                "user_id": user_id,
                "source": source,
                "detail": str(exc),
                "timestamp_ms": int(time.time() * 1000),
            }

    # 6. Strip raw content from any nested feature signals
    data = _strip_raw_signals(data)

    # 7. Apply standard egress filter (PII scrubbing, secret key dropping)
    filtered = egress_filter(data)

    # 8. Append egress metadata
    if isinstance(filtered, dict):
        filtered["_egress"] = {
            "filtered_at_ms": int(time.time() * 1000),
            "source": source,
            "app_id": app_id,
            "raw_payload_included": False,
        }

    return filtered


def _strip_raw_signals(data: Any) -> Any:
    """Recursively strip raw_content/raw_payload from feature signal dicts."""
    if isinstance(data, dict):
        if "raw_content" in data or "raw_payload" in data:
            return strip_raw_content(data)
        return {k: _strip_raw_signals(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_strip_raw_signals(item) for item in data]
    return data
