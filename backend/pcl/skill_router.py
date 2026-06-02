import re
from typing import Any, Optional

from database import list_pcl_skills
from pcl.memory import read_memory_file


_TOKEN_RE = re.compile(r"[a-z0-9]+")

_INTENT_HINTS = {
    "writing": {
        "write", "draft", "reply", "email", "message", "tone", "voice",
        "style", "copy", "summarize",
    },
    "calendar": {
        "calendar", "schedule", "meeting", "week", "plan", "availability",
        "tomorrow", "today", "reminder",
    },
    "coding": {
        "code", "review", "pr", "pull", "request", "bug", "test", "repo",
        "function", "api", "backend", "frontend",
    },
    "research": {
        "research", "paper", "compare", "find", "learn", "explain",
        "source", "summary", "market",
    },
}


def route_skill_request(
    message: str,
    intent: str = "",
    category: Optional[str] = None,
    max_skills: int = 3,
    user_id: str = "local_user",
    include_memory: bool = False,
) -> dict[str, Any]:
    text = " ".join(part for part in [message, intent, category or ""] if part).strip()
    query_tokens = _tokens(text)
    skills = list_pcl_skills(category=category, active_only=True, limit=200)

    scored = []
    for skill in skills:
        score, reasons = _score_skill(skill, query_tokens, intent=intent, category=category)
        if score > 0:
            scored.append((score, reasons, skill))

    scored.sort(key=lambda item: (-item[0], item[2]["name"]))
    selected = [
        {
            **skill,
            "score": round(score, 3),
            "reason_codes": reasons,
        }
        for score, reasons, skill in scored[: max(1, min(max_skills, 10))]
    ]

    memory_scopes = _unique(scope for skill in selected for scope in skill["memory_scopes"])
    response = {
        "query": {
            "message": message,
            "intent": intent,
            "category": category,
            "max_skills": max_skills,
            "user_id": user_id,
        },
        "skills": selected,
        "selected_skill_ids": [skill["skill_id"] for skill in selected],
        "memory_scopes": memory_scopes,
        "required_tools": _unique(tool for skill in selected for tool in skill["required_tools"]),
        "privacy_rules": _unique(rule for skill in selected for rule in skill["privacy_rules"]),
    }
    if include_memory:
        response["memory"] = [
            {
                "scope": memory["scope"],
                "content": memory["content"],
                "updated_at": memory["updated_at"],
            }
            for memory in (read_memory_file(user_id, scope) for scope in memory_scopes)
        ]
    return response


def _score_skill(
    skill: dict[str, Any],
    query_tokens: set[str],
    intent: str = "",
    category: Optional[str] = None,
) -> tuple[float, list[str]]:
    haystack = " ".join(
        [
            skill.get("skill_id", ""),
            skill.get("name", ""),
            skill.get("category", ""),
            skill.get("description", ""),
            skill.get("instructions", ""),
            " ".join(skill.get("memory_scopes") or []),
            " ".join(skill.get("required_tools") or []),
        ]
    )
    skill_tokens = _tokens(haystack)
    overlap = query_tokens & skill_tokens
    score = float(len(overlap))
    reasons = []

    if overlap:
        reasons.append("keyword_overlap")

    skill_category = skill.get("category") or "general"
    if category and skill_category == category:
        score += 3.0
        reasons.append("category_filter")

    if intent and skill_category in _tokens(intent):
        score += 2.0
        reasons.append("intent_category")

    hinted_categories = [
        hint_category
        for hint_category, hints in _INTENT_HINTS.items()
        if query_tokens & hints
    ]
    if skill_category in hinted_categories:
        score += 2.5
        reasons.append("intent_hint")

    skill_id_tokens = _tokens(skill.get("skill_id", "").replace("-", " "))
    if query_tokens & skill_id_tokens:
        score += 1.5
        reasons.append("skill_id_match")

    return score, reasons


def _tokens(value: str) -> set[str]:
    return set(_TOKEN_RE.findall((value or "").lower()))


def _unique(values) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
