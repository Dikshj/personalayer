import math
import re
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from urllib.parse import urlparse

from collectors.signal_extractor import extract_signals
from database import get_persona_feedback, get_persona_signals_last_n_days, insert_persona_signal


TOPIC_KEYWORDS = {
    "ai_agents": ["ai agent", "agents", "mcp", "tool use", "autonomous agent"],
    "personal_data": ["personal data", "privacy", "data vault", "oauth", "consent"],
    "developer_tools": ["sdk", "api", "github", "cursor", "claude code", "devtool"],
    "startups": ["startup", "founder", "yc", "product market", "saas"],
    "email_productivity": ["gmail", "inbox", "email", "newsletter", "followup"],
    "video_learning": ["youtube", "tutorial", "course", "walkthrough"],
}

DOMAIN_TOPICS = {
    "github.com": "developer_tools",
    "youtube.com": "video_learning",
    "youtu.be": "video_learning",
    "linkedin.com": "professional_networking",
    "x.com": "social_research",
    "twitter.com": "social_research",
    "mail.google.com": "email_productivity",
}


def _now_ms() -> int:
    return int(time.time() * 1000)


def _normalize_topic(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9+#.]+", "_", value)
    return value.strip("_")


def _domain_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def _keyword_topics(text: str) -> list[str]:
    lowered = text.lower()
    topics = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            topics.append(topic)
    return topics


def record_browsing_signals(
    url: str,
    title: str,
    time_spent_seconds: int,
    search_query: str | None,
    timestamp: int | None = None,
) -> None:
    timestamp = timestamp or _now_ms()
    domain = _domain_from_url(url)
    evidence = search_query or title or domain
    text = " ".join(part for part in [title, search_query or "", domain] if part)

    if domain:
        insert_persona_signal(
            "browser",
            "domain",
            domain,
            weight=max(0.5, min(time_spent_seconds / 120, 3.0)),
            confidence=0.45,
            evidence=evidence,
            timestamp=timestamp,
            shareable=False,
        )
        if domain in DOMAIN_TOPICS:
            insert_persona_signal(
                "browser",
                "interest",
                DOMAIN_TOPICS[domain],
                weight=0.8,
                confidence=0.5,
                evidence=domain,
                timestamp=timestamp,
            )

    for topic in _keyword_topics(text):
        insert_persona_signal(
            "browser",
            "interest",
            topic,
            weight=1.2,
            confidence=0.65,
            evidence=evidence,
            timestamp=timestamp,
        )

    signals = extract_signals(text)
    for language in signals.get("languages", []):
        insert_persona_signal("browser", "skill", language, 1.0, 0.6, evidence, timestamp)
    for framework in signals.get("frameworks", []):
        insert_persona_signal("browser", "tool", framework, 1.0, 0.6, evidence, timestamp)
    if signals.get("task"):
        insert_persona_signal("browser", "task_pattern", signals["task"], 0.8, 0.55, evidence, timestamp)
    if signals.get("domain"):
        insert_persona_signal("browser", "work_domain", signals["domain"], 1.0, 0.6, evidence, timestamp)


def record_feed_signals(
    source: str,
    content_type: str,
    content: str,
    author: str = "",
    url: str = "",
    timestamp: int | None = None,
) -> None:
    timestamp = timestamp or _now_ms()
    evidence = " ".join(part for part in [content[:220], author, url] if part)
    text = f"{source} {content_type} {content} {author} {url}"

    insert_persona_signal(source, "platform_activity", content_type, 0.7, 0.45, evidence, timestamp)

    for topic in _keyword_topics(text):
        insert_persona_signal(source, "interest", topic, 1.4, 0.7, evidence, timestamp)

    signals = extract_signals(text)
    for language in signals.get("languages", []):
        insert_persona_signal(source, "skill", language, 1.1, 0.65, evidence, timestamp)
    for framework in signals.get("frameworks", []):
        insert_persona_signal(source, "tool", framework, 1.1, 0.65, evidence, timestamp)
    if signals.get("task"):
        insert_persona_signal(source, "task_pattern", signals["task"], 0.9, 0.6, evidence, timestamp)
    if signals.get("domain"):
        insert_persona_signal(source, "work_domain", signals["domain"], 1.1, 0.65, evidence, timestamp)


def _decayed_weight(signal: dict, half_life_days: int = 14) -> float:
    age_ms = max(0, _now_ms() - int(signal["timestamp"]))
    age_days = age_ms / (1000 * 60 * 60 * 24)
    decay = math.pow(0.5, age_days / half_life_days)
    return float(signal["weight"]) * float(signal["confidence"]) * decay


def _feedback_rules() -> dict[tuple[str, str], str]:
    rules = {}
    for item in reversed(get_persona_feedback()):
        rules[(item["signal_type"], _normalize_topic(item["name"]))] = item["action"]
    return rules


def _aggregate(signals: list[dict], feedback: dict[tuple[str, str], str] | None = None) -> dict:
    feedback = feedback or {}
    scores: dict[str, Counter] = defaultdict(Counter)
    sources: dict[tuple[str, str], set[str]] = defaultdict(set)
    evidence: dict[tuple[str, str], list[str]] = defaultdict(list)

    for signal in signals:
        signal_type = signal["signal_type"]
        name = _normalize_topic(signal["name"])
        if not name:
            continue
        action = feedback.get((signal_type, name))
        if action in {"reject", "hide"}:
            continue
        score = _decayed_weight(signal)
        if action == "confirm":
            score *= 1.25
        elif action == "boost":
            score *= 1.5
        scores[signal_type][name] += score
        sources[(signal_type, name)].add(signal["source"])
        if signal.get("evidence") and len(evidence[(signal_type, name)]) < 3:
            evidence[(signal_type, name)].append(signal["evidence"])

    output = {}
    for signal_type, counter in scores.items():
        rows = []
        for name, score in counter.most_common(12):
            source_count = len(sources[(signal_type, name)])
            cross_source_boost = 1 + min(source_count - 1, 3) * 0.15
            final_score = min(score * cross_source_boost, 10.0)
            rows.append({
                "name": name,
                "score": round(final_score, 3),
                "confidence": round(min(0.35 + final_score / 10 + source_count * 0.08, 0.95), 3),
                "sources": sorted(sources[(signal_type, name)]),
                "evidence": evidence[(signal_type, name)],
            })
        output[signal_type] = rows
    return output


def build_living_persona(days: int = 30) -> dict:
    signals = get_persona_signals_last_n_days(days, shareable_only=True)
    recent = get_persona_signals_last_n_days(7, shareable_only=True)
    previous = [
        s for s in signals
        if int(s["timestamp"]) < _now_ms() - (7 * 24 * 60 * 60 * 1000)
    ]

    feedback = _feedback_rules()
    aggregate = _aggregate(signals, feedback)
    recent_scores = _aggregate(recent, feedback)
    previous_scores = _aggregate(previous, feedback)

    trends = []
    for item in recent_scores.get("interest", [])[:10]:
        previous_score = next(
            (p["score"] for p in previous_scores.get("interest", []) if p["name"] == item["name"]),
            0,
        )
        direction = "rising" if item["score"] > previous_score * 1.25 else "steady"
        trends.append({
            "name": item["name"],
            "direction": direction,
            "recent_score": item["score"],
            "previous_score": previous_score,
        })

    return {
        "interests": aggregate.get("interest", []),
        "skills": aggregate.get("skill", []),
        "tools": aggregate.get("tool", []),
        "work_domains": aggregate.get("work_domain", []),
        "task_patterns": aggregate.get("task_pattern", []),
        "trends": trends,
        "meta": {
            "updated_at": datetime.now(UTC).isoformat(),
            "data_window_days": days,
            "signal_count": len(signals),
            "model": "local_recency_weighted_signals_v1",
        },
    }
