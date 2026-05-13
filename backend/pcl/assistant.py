import os
from typing import Any

import httpx

from database import list_feature_signals
from pcl.contextlayer import build_context_bundle, get_contextlayer_activity
from pcl.profile import build_local_user_context_profile
from pcl.proxy import _extract_bearer_token


DEFAULT_ASSISTANT_MODEL = "gpt-4.1-mini"


def build_personal_assistant_system_prompt(user_id: str) -> tuple[str, dict[str, Any]]:
    profile = build_local_user_context_profile(user_id)
    bundle = build_context_bundle(
        user_id=user_id,
        app_id="contextlayer_assistant",
        intent="full_profile",
        requested_scopes=["assistant"],
        source="assistant",
    )
    signals = list_feature_signals(user_id=user_id, active_only=True)[:10]
    activity = get_contextlayer_activity(user_id=user_id, limit=10)

    top_features = [
        {
            "app_id": signal["app_id"],
            "feature_id": signal["feature_id"],
            "recency_score": round(float(signal["recency_score"]), 3),
            "tier": signal["tier"],
        }
        for signal in signals
    ]

    prompt = (
        "You are the user's personal context assistant. You have access to their "
        "behavioral profile built from app usage patterns.\n\n"
        f"Identity: {profile.identity.role or 'unknown'} in {profile.identity.domain or 'unknown'}, "
        f"{profile.identity.skill_level or 'unknown'} skill level\n"
        f"Abstract profile: {bundle.get('abstract_attributes') or []}\n"
        f"Top used features: {top_features}\n"
        f"Behavior patterns: {profile.behavior.model_dump()}\n"
        f"Current activity: {bundle.get('active_context')}\n"
        f"Preferences: {[pref.model_dump() for pref in profile.explicit_preferences]}\n\n"
        "Answer questions about usage patterns, suggest improvements, and help the user "
        "understand their own context. Be specific. Use their actual data. Never reveal "
        "raw feature signals; only synthesized insights."
    )
    context = {
        "bundle": bundle,
        "profile": profile.model_dump(),
        "top_features": top_features,
        "recent_activity_counts": {
            "raw_events": len(activity["raw_events"]),
            "query_log": len(activity["query_log"]),
            "feedback_events": len(activity["feedback_events"]),
        },
    }
    return prompt, context


async def personal_assistant_chat(
    message: str,
    user_id: str = "local_user",
    model: str = DEFAULT_ASSISTANT_MODEL,
    authorization: str = "",
) -> dict[str, Any]:
    if not message.strip():
        return {"status": "error", "error": "message_required"}

    system_prompt, context = build_personal_assistant_system_prompt(user_id)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message.strip()},
    ]

    upstream_key = _extract_bearer_token(authorization) or os.getenv("OPENAI_API_KEY", "")
    upstream_base = os.getenv("CONTEXTLAYER_UPSTREAM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    payload = {"model": model, "messages": messages, "temperature": 0.2}

    if not upstream_key:
        return {
            "status": "dry_run",
            "upstream": "not_configured",
            "message": _local_assistant_summary(message, context),
            "context": {
                "bundle_id": context["bundle"]["bundle_id"],
                "top_features": context["top_features"],
                "recent_activity_counts": context["recent_activity_counts"],
            },
            "payload": {
                "model": payload["model"],
                "messages": [
                    {"role": item["role"], "content_length": len(item["content"])}
                    for item in payload["messages"]
                ],
                "temperature": payload["temperature"],
            },
        }

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{upstream_base}/chat/completions",
            headers={
                "Authorization": f"Bearer {upstream_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    response.raise_for_status()
    data = response.json()
    return {
        "status": "ok",
        "context": {
            "bundle_id": context["bundle"]["bundle_id"],
            "top_features": context["top_features"],
        },
        "response": data,
    }


def _local_assistant_summary(message: str, context: dict[str, Any]) -> str:
    top = context["top_features"][:3]
    active = context["bundle"].get("active_context") or {}
    project = active.get("project") or active.get("current_project") or "unknown"
    if not top:
        return (
            "I do not have enough behavioral signal yet. Start using tracked app "
            "features or complete onboarding so ContextLayer can build a useful profile."
        )

    feature_text = ", ".join(f"{item['app_id']}:{item['feature_id']}" for item in top)
    return (
        f"Based on current ContextLayer data, your strongest recent signals are {feature_text}. "
        f"Current project is {project}. I would use these as synthesized context for: {message.strip()}"
    )
