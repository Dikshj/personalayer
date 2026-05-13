from __future__ import annotations

import time
from typing import Any

import httpx


class PersonalContextLayer:
    def __init__(
        self,
        app_id: str,
        base_url: str = "http://127.0.0.1:7823",
        api_key: str = "",
        user_token: str = "",
    ):
        self.app_id = app_id
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.user_token = user_token

    def register_app(self, name: str, allowed_layers: list[str]) -> dict[str, Any]:
        return self._post("/pcl/apps", {
            "app_id": self.app_id,
            "name": name,
            "allowed_layers": allowed_layers,
        })

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

    def revoke_app(self) -> dict[str, Any]:
        return self._post(f"/pcl/apps/{self.app_id}/revoke", {})

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

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = httpx.get(
            f"{self.base_url}{path}",
            params=params,
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}{path}",
            json=payload,
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def _delete(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = httpx.delete(
            f"{self.base_url}{path}",
            params=params,
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

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
