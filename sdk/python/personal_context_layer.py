from __future__ import annotations

import json
import time
from typing import Any

import httpx


class PCLAuthError(Exception):
    """Raised on authentication or authorization failures."""
    pass


class PCLConsentError(Exception):
    """Raised when app consent is missing, revoked, or insufficient."""
    pass


class PCLPrivacyError(Exception):
    """Raised when a privacy boundary blocks a request."""
    pass


class PCLTimeoutError(Exception):
    """Raised when a request exceeds the configured timeout."""
    pass


class PCLServerError(Exception):
    """Raised on 5xx or unexpected server errors."""
    pass


class PersonalContextLayer:
    """Production-ready Python SDK for PersonaLayer.

    All outbound requests carry the app's api_key and (optionally) a user_token.
    The backend enforces egress privacy filtering on every response path.
    """

    def __init__(
        self,
        app_id: str,
        base_url: str = "http://127.0.0.1:7823",
        api_key: str = "",
        user_token: str = "",
        timeout: float = 10.0,
        max_retries: int = 3,
        retry_backoff: float = 0.5,
    ):
        if not app_id:
            raise ValueError("app_id is required")
        self.app_id = app_id
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.user_token = user_token
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff

    # ── App registration ──────────────────────────────────────────────────────────────────────

    def register_app(self, name: str, allowed_layers: list[str]) -> dict[str, Any]:
        return self._post("/pcl/apps", {
            "app_id": self.app_id,
            "name": name,
            "allowed_layers": allowed_layers,
        })

    # ── Ingest ─────────────────────────────────────────────────────────────────────────────

    def track_feature(
        self,
        user_id: str,
        feature_id: str,
        feature_name: str = "",
        event_type: str = "used",
        weight: float = 1.0,
    ) -> dict[str, Any]:
        return self._post("/pcl/events/feature", {
            "app_id": self.app_id,
            "user_id": user_id,
            "feature_id": feature_id,
            "feature_name": feature_name,
            "event_type": event_type,
            "weight": weight,
            "timestamp": int(time.time() * 1000),
        })

    def track(
        self,
        feature_id: str,
        user_id: str = "local_user",
        action: str = "used",
        session_id: str = "",
        timestamp: int | None = None,
        is_synthetic: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not feature_id:
            raise ValueError("feature_id is required")
        return self._post("/v1/ingest/sdk", {
            "app_id": self.app_id,
            "user_id": user_id,
            "feature_id": _normalize_feature_id(feature_id),
            "action": action,
            "session_id": session_id,
            "timestamp": timestamp or int(time.time() * 1000),
            "is_synthetic": is_synthetic,
            "metadata": metadata or {},
        })

    # ── Cold start / onboarding ─────────────────────────────────────0─────────────────────────────

    def generate_cold_start(
        self,
        user_id: str = "local_user",
        app_name: str | None = None,
        features: list[str] | None = None,
        role: str = "",
        domain: str = "",
        skill_level: str = "intermediate",
    ) -> dict[str, Any]:
        return self._post("/v1/context/cold-start", {
            "app_id": self.app_id,
            "app_name": app_name or self.app_id,
            "user_id": user_id,
            "features": features or [],
            "role": role,
            "domain": domain,
            "skill_level": skill_level,
        })

    # ── Query / bundle ─────────────────────────────────────────────────────────────────────────────

    def personalize(
        self,
        user_id: str,
        features: list[dict[str, Any]],
        requested_layers: list[str] | None = None,
        purpose: str = "ui_personalization",
    ) -> dict[str, Any]:
        return self._post("/pcl/query", {
            "app_id": self.app_id,
            "user_id": user_id,
            "purpose": purpose,
            "requested_layers": requested_layers or [],
            "features": features,
        })

    def get_context_bundle(
        self,
        user_id: str = "local_user",
        intent: str = "full_profile",
        requested_scopes: list[str] | None = None,
    ) -> dict[str, Any]:
        return self._post("/v1/context/bundle", {
            "app_id": self.app_id,
            "user_id": user_id,
            "intent": intent,
            "requested_scopes": requested_scopes or [],
        })

    # ── Consent helpers ──────────────────────────────────────────────────────────────────────────────

    def ensure_consent(self, user_id: str, scopes: list[str]) -> dict[str, Any]:
        """Request consent for scopes if not already granted.

        Raises PCLConsentError if the user denies or revokes consent.
        """
        resp = self._post("/pcl/permissions", {
            "app_id": self.app_id,
            "user_id": user_id,
            "scopes": scopes,
        })
        if resp.get("status") != "granted":
            raise PCLConsentError(
                f"Consent not granted for {self.app_id}: {resp.get('reason', 'unknown')}"
            )
        return resp

    def revoke_app(self) -> dict[str, Any]:
        return self._post(f"/pcl/apps/{self.app_id}/revoke", {})

    # ── Heartbeat / feedback ──────────────────────────────────────────────────────────────────────────

    def heartbeat(
        self,
        user_id: str = "local_user",
        project: str = "",
        active_apps: list[str] | None = None,
        inferred_intent: str = "",
        session_depth: str = "shallow",
    ) -> dict[str, Any]:
        return self._post("/v1/context/heartbeat", {
            "user_id": user_id,
            "project": project,
            "active_apps": active_apps or [self.app_id],
            "inferred_intent": inferred_intent,
            "session_depth": session_depth,
        })

    def feedback(
        self,
        bundle_id: str,
        outcome: str,
        features_actually_used: list[str] | None = None,
        user_id: str = "local_user",
    ) -> dict[str, Any]:
        if not bundle_id:
            raise ValueError("bundle_id is required")
        if not outcome:
            raise ValueError("outcome is required")
        return self._post("/v1/context/feedback", {
            "app_id": self.app_id,
            "user_id": user_id,
            "bundle_id": bundle_id,
            "outcome": outcome,
            "features_actually_used": [
                _normalize_feature_id(feature_id)
                for feature_id in (features_actually_used or [])
            ],
        })

    # ── Deletion / export ───────────────────────────────────────────────────────────────────────────────

    def delete_app_data(self) -> dict[str, Any]:
        return self._delete(f"/pcl/apps/{self.app_id}/data")

    def clear_query_log(self, user_id: str | None = None) -> dict[str, Any]:
        params = {"app_id": self.app_id}
        if user_id:
            params["user_id"] = user_id
        return self._delete("/pcl/query-log", params=params)

    def activity(self, user_id: str = "local_user", limit: int = 100) -> dict[str, Any]:
        return self._get("/v1/context/activity", params={"user_id": user_id, "limit": limit})

    def delete_user_data(self, user_id: str) -> dict[str, Any]:
        return self._delete(f"/pcl/users/{user_id}/data")

    def delete_all_context(self, user_id: str = "local_user") -> dict[str, Any]:
        return self._delete("/v1/context/all", params={"user_id": user_id})

    # ── Low-level transport with retry ─────────────────────────────────────────────────────────────────────────

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        headers = self._headers()
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        url = f"{self.base_url}{path}"
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                method_upper = method.upper()
                if method_upper == "GET":
                    return httpx.get(url, headers=headers, timeout=self.timeout, **kwargs)
                if method_upper == "POST":
                    return httpx.post(url, headers=headers, timeout=self.timeout, **kwargs)
                if method_upper == "DELETE":
                    return httpx.delete(url, headers=headers, timeout=self.timeout, **kwargs)
                return httpx.request(method_upper, url, headers=headers, timeout=self.timeout, **kwargs)
            except httpx.TimeoutException as exc:
                last_exc = exc
                time.sleep(self.retry_backoff * (2 ** attempt))
            except httpx.ConnectError as exc:
                last_exc = exc
                time.sleep(self.retry_backoff * (2 ** attempt))
        raise PCLTimeoutError(f"Request to {url} failed after {self.max_retries} retries") from last_exc

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        resp = self._request("GET", path, params=params)
        return _handle_response(resp)

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self._request("POST", path, json=payload)
        return _handle_response(resp)

    def _delete(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        resp = self._request("DELETE", path, params=params)
        return _handle_response(resp)

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.user_token:
            headers["x-user-token"] = self.user_token
        return headers


def _normalize_feature_id(feature_id: str) -> str:
    normalized = []
    previous_dash = False
    for char in feature_id.lower():
        if char.isalnum():
            normalized.append(char)
            previous_dash = False
        elif not previous_dash:
            normalized.append("-")
            previous_dash = True
    return "".join(normalized).strip("-")


def _handle_response(resp: httpx.Response) -> dict[str, Any]:
    try:
        body = resp.json()
    except json.JSONDecodeError:
        body = {"raw": resp.text}
    status_code = getattr(resp, "status_code", 200)
    if status_code == 401:
        raise PCLAuthError(body.get("detail", "Unauthorized"))
    if status_code == 403:
        raise PCLPrivacyError(body.get("detail", "Forbidden"))
    if status_code == 409 and "consent" in body.get("detail", "").lower():
        raise PCLConsentError(body.get("detail", "Consent required"))
    if status_code >= 500:
        raise PCLServerError(body.get("detail", f"Server error {status_code}"))
    resp.raise_for_status()
    return body
