import os
from typing import Any

import httpx

from database import list_feature_signals
from pcl.contextlayer import build_context_bundle, get_contextlayer_activity
from pcl.profile import build_local_user_context_profile
from pcl.privacy import egress_filter
from pcl.proxy import _extract_bearer_token
from pcl.skill_router import route_skill_request


DEFAULT_ASSISTANT_MODEL = "gpt-4.1-mini"


def build_personal_assistant_system_prompt(
    user_id: str,
    message: str = "",
) -> tuple[str, dict[str, Any]]:
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
    skill_route = route_skill_request(
        message=message,
        user_id=user_id,
        max_skills=3,
        include_memory=True,
    ) if message.strip() else {
        "skills": [],
        "selected_skill_ids": [],
        "memory_scopes": [],
        "required_tools": [],
        "privacy_rules": [],
        "memory": [],
    }
    skill_prompt = _format_skill_prompt(skill_route)

    prompt = (
        "You are the user's personal context assistant. You have access to their "
        "behavioral profile built from app usage patterns.\n\n"
        f"Identity: {profile.identity.role or 'unknown'} in {profile.identity.domain or 'unknown'}, "
        f"{profile.identity.skill_level or 'unknown'} skill level\n"
        f"Abstract profile: {egress_filter(bundle.get('abstract_attributes')) or []}\n"
        f"Top used features: {egress_filter(top_features)}\n"
        f"Behavior patterns: {egress_filter(profile.behavior.model_dump())}\n"
        f"Current activity: {egress_filter(bundle.get('active_context'))}\n"
        f"Preferences: {egress_filter([pref.model_dump() for pref in profile.explicit_preferences])}\n\n"
        f"{skill_prompt}"
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
        "skill_route": skill_route,
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

    system_prompt, context = build_personal_assistant_system_prompt(user_id, message=message)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message.strip()},
    ]

    upstream_key = _extract_bearer_token(authorization) or os.getenv("OPENAI_API_KEY", "")
    upstream_base = os.getenv("CONTEXTLAYER_UPSTREAM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    payload = {"model": model, "messages": messages, "temperature": 0.2}

    if not upstream_key:
        if os.getenv("PERSONALAYER_DEV_MODE") != "1":
            return {
                "status": "error",
                "error": "upstream_not_configured",
                "detail": "Set OPENAI_API_KEY or enable PERSONALAYER_DEV_MODE=1",
            }
        return {
            "status": "dry_run",
            "upstream": "not_configured",
            "message": _local_assistant_summary(message, context),
            "context": {
                "bundle_id": context["bundle"]["bundle_id"],
                "top_features": context["top_features"],
                "recent_activity_counts": context["recent_activity_counts"],
                "selected_skill_ids": context["skill_route"]["selected_skill_ids"],
                "memory_scopes": context["skill_route"]["memory_scopes"],
                "privacy_rules": context["skill_route"]["privacy_rules"],
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
            "selected_skill_ids": context["skill_route"]["selected_skill_ids"],
            "memory_scopes": context["skill_route"]["memory_scopes"],
        },
        "response": data,
    }


def _format_skill_prompt(skill_route: dict[str, Any]) -> str:
    skills = skill_route.get("skills") or []
    memory = skill_route.get("memory") or []
    privacy_rules = skill_route.get("privacy_rules") or []
    if not skills and not memory and not privacy_rules:
        return ""

    lines = ["Selected task skills:"]
    for skill in skills:
        lines.append(
            f"- {skill['skill_id']} ({skill['category']}): {skill.get('description') or skill['name']}"
        )
        if skill.get("instructions"):
            lines.append(f"  Instructions: {skill['instructions']}")
        if skill.get("memory_scopes"):
            lines.append(f"  Memory scopes: {', '.join(skill['memory_scopes'])}")

    if memory:
        lines.append("\nApproved Markdown memory:")
        for item in memory:
            lines.append(f"## {item['scope']}\n{item['content'].strip()}")

    if privacy_rules:
        lines.append("\nSkill privacy rules:")
        for rule in privacy_rules:
            lines.append(f"- {rule}")

    lines.append("")
    return "\n".join(lines) + "\n"


def _local_assistant_summary(message: str, context: dict[str, Any]) -> str:
    top = context["top_features"][:3]
    active = context["bundle"].get("active_context") or {}
    project = active.get("project") or active.get("current_project") or "unknown"
    selected_skills = context.get("skill_route", {}).get("selected_skill_ids") or []
    if not top:
        base = (
            "I do not have enough behavioral signal yet. Start using tracked app "
            "features or complete onboarding so ContextLayer can build a useful profile."
        )
        if selected_skills:
            return f"{base} Selected skills for this request: {', '.join(selected_skills)}."
        return base

    feature_text = ", ".join(f"{item['app_id']}:{item['feature_id']}" for item in top)
    skill_text = (
        f" Selected skills: {', '.join(selected_skills)}."
        if selected_skills else ""
    )
    return (
        f"Based on current ContextLayer data, your strongest recent signals are {feature_text}. "
        f"Current project is {project}. I would use these as synthesized context for: {message.strip()}"
        f"{skill_text}"
    )
