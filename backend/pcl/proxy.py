import os
from typing import Any

import httpx

from pcl.contextlayer import authorize_developer_context_request, build_context_bundle


CONTEXT_TOKEN = "{cl_context}"


def inject_context_steering(
    payload: dict[str, Any],
    user_id: str = "local_user",
    app_id: str = "human_api_proxy",
    context_authorization: str = "",
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    messages = payload.get("messages")
    if not isinstance(messages, list):
        raise ValueError("messages must be a list")

    if not _contains_context_token(messages):
        return payload, None

    auth = authorize_developer_context_request(
        authorization=context_authorization,
        user_id=user_id,
        app_id=app_id,
        requested_scopes=["context_steering"],
    )
    if not auth["authorized"]:
        return {"error": auth["error"], "auth": auth}, None

    bundle = build_context_bundle(
        user_id=user_id,
        app_id=app_id,
        intent="full_profile",
        requested_scopes=["context_steering"],
        source="proxy",
    ) | {"auth": auth}
    prefix = build_context_steering_prefix(bundle)
    cleaned_messages = [
        {
            **message,
            "content": _clean_context_token(message.get("content")),
        }
        for message in messages
        if isinstance(message, dict)
    ]

    steered_payload = {
        **payload,
        "messages": [
            {"role": "system", "content": prefix},
            *cleaned_messages,
        ],
    }
    return steered_payload, bundle


def build_context_steering_prefix(bundle: dict[str, Any]) -> str:
    active_context = bundle.get("active_context") or {}
    abstract = bundle.get("abstract_attributes") or []
    abstract_labels = []
    for item in abstract[:3]:
        if isinstance(item, dict) and item.get("attribute"):
            abstract_labels.append(str(item["attribute"]))
        elif isinstance(item, str):
            abstract_labels.append(item)

    return (
        "[ContextLayer user profile]\n"
        f"features_used: {', '.join(bundle.get('features') or [])}\n"
        f"style: {bundle.get('style')}\n"
        f"timing: {bundle.get('timing')}\n"
        f"current_project: {active_context.get('project') or active_context.get('current_project') or 'unknown'}\n"
        f"constraints: {bundle.get('constraints') or {}}\n"
        f"abstract: {', '.join(abstract_labels)}\n"
        "[End context]"
    )


async def proxy_chat_completion(
    payload: dict[str, Any],
    user_id: str = "local_user",
    app_id: str = "human_api_proxy",
    authorization: str = "",
    context_authorization: str = "",
) -> dict[str, Any]:
    context_authorization = context_authorization or _context_authorization_from_headers(authorization)
    steered_payload, bundle = inject_context_steering(
        payload,
        user_id=user_id,
        app_id=app_id,
        context_authorization=context_authorization,
    )
    if isinstance(steered_payload, dict) and steered_payload.get("error"):
        return steered_payload
    upstream_key = _upstream_key_from_authorization(authorization) or os.getenv("OPENAI_API_KEY", "")
    upstream_base = os.getenv("CONTEXTLAYER_UPSTREAM_BASE_URL", "https://api.openai.com/v1").rstrip("/")

    if not upstream_key:
        return {
            "status": "dry_run",
            "context_injected": bundle is not None,
            "bundle_id": bundle.get("bundle_id") if bundle else None,
            "upstream": "not_configured",
            "payload": steered_payload,
        }

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{upstream_base}/chat/completions",
            headers={
                "Authorization": f"Bearer {upstream_key}",
                "Content-Type": "application/json",
            },
            json=steered_payload,
        )
    response.raise_for_status()
    return response.json()


def _contains_context_token(messages: list[Any]) -> bool:
    return any(
        isinstance(message, dict)
        and CONTEXT_TOKEN in str(message.get("content", ""))
        for message in messages
    )


def _clean_context_token(content: Any) -> Any:
    if isinstance(content, str):
        return content.replace(CONTEXT_TOKEN, "").strip()
    if isinstance(content, list):
        cleaned = []
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                cleaned.append({**part, "text": part["text"].replace(CONTEXT_TOKEN, "").strip()})
            else:
                cleaned.append(part)
        return cleaned
    return content


def _extract_bearer_token(authorization: str) -> str:
    if not authorization:
        return ""
    prefix = "bearer "
    if authorization.lower().startswith(prefix):
        return authorization[len(prefix):].strip()
    return ""


def _context_authorization_from_headers(authorization: str) -> str:
    token = _extract_bearer_token(authorization)
    if token.startswith("cl_"):
        return f"Bearer {token}"
    return ""


def _upstream_key_from_authorization(authorization: str) -> str:
    token = _extract_bearer_token(authorization)
    if token.startswith("cl_"):
        return ""
    return token
