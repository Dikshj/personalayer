from __future__ import annotations

import hashlib
import json
from typing import Any

import database
from pcl.privacy import egress_filter


MAX_ATTRIBUTE_BYTES = 4096
ALLOWED_SEVERITIES = {"debug", "info", "warning", "error"}


def record_observability_event(
    user_id: str,
    source: str,
    event_name: str,
    severity: str = "info",
    route: str = "",
    status_code: int | None = None,
    duration_ms: int | None = None,
    attributes: dict[str, Any] | None = None,
) -> dict:
    safe_attributes = sanitize_observability_attributes(attributes or {})
    canonical = json.dumps(
        {
            "user_id": user_id,
            "source": source,
            "event_name": event_name,
            "severity": severity,
            "route": route,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "attributes": safe_attributes,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return database.insert_observability_event(
        user_id=user_id,
        source=source,
        event_name=event_name,
        severity=severity if severity in ALLOWED_SEVERITIES else "info",
        route=route,
        status_code=status_code,
        duration_ms=duration_ms,
        attributes=safe_attributes,
        event_hash=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    )


def list_observability_events(
    user_id: str,
    source: str | None = None,
    severity: str | None = None,
    limit: int = 100,
) -> dict:
    return {
        "user_id": user_id,
        "events": database.list_observability_events(
            user_id=user_id,
            source=source,
            severity=severity,
            limit=limit,
        ),
    }


def sanitize_observability_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    filtered = egress_filter(attributes)
    if not isinstance(filtered, dict):
        return {}
    encoded = json.dumps(filtered, sort_keys=True)
    if len(encoded.encode("utf-8")) <= MAX_ATTRIBUTE_BYTES:
        return filtered
    return {
        "truncated": True,
        "attribute_keys": sorted(str(key)[:80] for key in filtered.keys()),
        "original_size_bytes": len(encoded.encode("utf-8")),
    }
