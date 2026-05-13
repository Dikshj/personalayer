import math
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime

from database import (
    get_context_access_logs,
    get_events_last_n_days,
    get_feed_items_last_n_days,
    get_persona_signals_last_n_days,
)
from living_persona import build_living_persona


LLM_SOURCES = {
    "chatgpt", "claude", "perplexity", "opencode", "cursor",
    "gemini", "grok", "github_copilot", "llm", "claude_code",
    "ollama", "aider", "sgpt",
}

TASK_TO_CONTEXT = {
    "debugging": ["current_goals", "skills", "priority_topics"],
    "building": ["current_goals", "skills", "communication_style"],
    "learning": ["learning_preferences", "priority_topics"],
    "reviewing": ["writing_preferences", "skills"],
    "deploying": ["current_goals", "skills"],
}

WORK_DOMAIN_TO_CONTEXT = {
    "ai_ml": ["priority_topics", "skills", "learning_preferences"],
    "web": ["skills", "current_goals"],
    "data": ["skills", "priority_topics"],
    "devops": ["skills", "current_goals"],
    "security": ["skills", "negative_preferences"],
}


def _now_ms() -> int:
    return int(time.time() * 1000)


def _age_score(timestamp: int, half_life_hours: int = 36) -> float:
    age_ms = max(0, _now_ms() - int(timestamp))
    age_hours = age_ms / (1000 * 60 * 60)
    return math.pow(0.5, age_hours / half_life_hours)


def _top(counter: Counter, limit: int = 5) -> list[dict]:
    if not counter:
        return []
    max_score = max(counter.values()) or 1
    rows = []
    for name, score in counter.most_common(limit):
        rows.append({
            "name": name,
            "score": round(float(score), 3),
            "confidence": round(min(0.25 + (score / max_score) * 0.65, 0.92), 3),
        })
    return rows


def predict_next_context(days: int = 14) -> dict:
    days = max(1, min(days, 90))
    signals = get_persona_signals_last_n_days(days, shareable_only=True)
    private_signals = get_persona_signals_last_n_days(days, shareable_only=False)
    events = get_events_last_n_days(days)
    feed_items = get_feed_items_last_n_days(days)
    logs = get_context_access_logs(limit=100)
    living = build_living_persona(days=days)

    task_scores: Counter = Counter()
    domain_scores: Counter = Counter()
    tool_scores: Counter = Counter()
    source_scores: Counter = Counter()
    context_scores: Counter = Counter()
    evidence: dict[str, list[str]] = defaultdict(list)

    for signal in signals:
        score = float(signal["weight"]) * float(signal["confidence"]) * _age_score(signal["timestamp"])
        name = signal["name"]
        if signal["signal_type"] == "task_pattern":
            task_scores[name] += score
            for field in TASK_TO_CONTEXT.get(name, []):
                context_scores[field] += score
        elif signal["signal_type"] == "work_domain":
            domain_scores[name] += score
            for field in WORK_DOMAIN_TO_CONTEXT.get(name, []):
                context_scores[field] += score * 0.8
        elif signal["signal_type"] == "tool":
            tool_scores[name] += score

        if signal.get("evidence") and len(evidence[name]) < 3:
            evidence[name].append(signal["evidence"])

    for signal in private_signals:
        if signal["signal_type"] == "domain":
            domain_scores[signal["name"]] += 0.15 * _age_score(signal["timestamp"])

    for item in feed_items:
        source = item["source"]
        score = _age_score(item["timestamp"])
        source_scores[source] += score
        if source in LLM_SOURCES:
            context_scores["current_goals"] += score * 1.2
            context_scores["skills"] += score * 0.6
        if item.get("content_type") in {"prompt", "session_signals"}:
            task_scores["active_llm_work"] += score * 0.7

    for event in events:
        domain = event.get("domain")
        if domain:
            domain_scores[domain] += min(event.get("time_spent_seconds", 0) / 300, 2.0) * _age_score(event["timestamp"])

    for log in logs:
        for field in log.get("fields_returned", []):
            context_scores[field] += 0.25

    top_tasks = _top(task_scores)
    top_domains = _top(domain_scores)
    top_tools = _top(tool_scores)
    top_sources = _top(source_scores)
    needed_context = _top(context_scores)

    leading_task = top_tasks[0]["name"] if top_tasks else "unknown"
    leading_domain = top_domains[0]["name"] if top_domains else "unknown"
    confidence_inputs = [
        len(signals) / 40,
        len(feed_items) / 20,
        len(events) / 50,
        0.3 if needed_context else 0,
    ]
    confidence = round(min(sum(confidence_inputs) / 3, 0.95), 3)

    return {
        "prediction": {
            "next_task": leading_task,
            "work_domain": leading_domain,
            "needed_context": needed_context,
            "recommended_action": _recommended_action(leading_task, needed_context),
            "confidence": confidence,
        },
        "signals": {
            "likely_tasks": top_tasks,
            "likely_domains": top_domains,
            "likely_tools": top_tools,
            "active_sources": top_sources,
        },
        "living_persona": {
            "interests": living.get("interests", [])[:5],
            "skills": living.get("skills", [])[:5],
            "trends": living.get("trends", [])[:5],
        },
        "evidence": evidence,
        "meta": {
            "updated_at": datetime.now(UTC).isoformat(),
            "data_window_days": days,
            "event_count": len(events),
            "feed_item_count": len(feed_items),
            "signal_count": len(signals),
            "model": "local_behavior_prediction_v1",
        },
    }


def _recommended_action(task: str, needed_context: list[dict]) -> str:
    fields = [item["name"] for item in needed_context[:3]]
    if task == "debugging":
        return "Prioritize recent project context, error history, and relevant skills."
    if task == "learning":
        return "Surface learning preferences, recent topics, and concise explanations."
    if task == "reviewing":
        return "Surface writing preferences, standards, and relevant technical skills."
    if task == "active_llm_work":
        return f"Preload context fields for the active AI tool: {', '.join(fields) or 'current_goals'}."
    if fields:
        return f"Preload context fields: {', '.join(fields)}."
    return "Collect more recent activity before making strong predictions."
