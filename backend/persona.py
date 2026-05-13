# backend/persona.py
import json
import logging
from collections import Counter
from pathlib import Path
from typing import Optional

from anthropic import Anthropic
from dotenv import load_dotenv

from database import create_tables, get_events_last_n_days, get_feed_items_last_n_days, save_persona

load_dotenv()
logger = logging.getLogger(__name__)

DATA_DIR = Path.home() / ".personalayer"
PERSONA_FILE = DATA_DIR / "persona.json"

PERSONA_SCHEMA = {
    "identity": {"role": "string", "expertise": [], "current_project": "string"},
    "voice": {"style": "string", "formality": "string", "emoji": False},
    "decisions": {
        "optimizes_for": "string",
        "risk_tolerance": "string",
        "instant_yes": [],
        "instant_no": [],
    },
    "context": {
        "building": "string",
        "blocked_on": "string",
        "learning_this_week": [],
        "active_hours": "string",
    },
    "interests": {
        "obsessions": [],
        "depth": {"expert": [], "learning": [], "shallow": []},
    },
    "values": {"trusts": [], "dislikes": []},
    "meta": {"updated_at": "ISO-8601", "data_window_days": 7, "event_count": 0},
}


def summarize_events(events: list[dict]) -> str:
    if not events:
        return ""

    domain_seconds: Counter = Counter()
    searches: list[str] = []
    titles: list[str] = []

    for e in events:
        if e.get("domain"):
            domain_seconds[e["domain"]] += e.get("time_spent_seconds", 0)
        if e.get("search_query"):
            searches.append(e["search_query"])
        if e.get("title"):
            titles.append(e["title"])

    lines = ["TOP DOMAINS (time spent in seconds):"]
    for domain, secs in domain_seconds.most_common(25):
        lines.append(f"  {domain}: {secs}s")

    if searches:
        unique_searches = list(dict.fromkeys(searches))[-60:]
        lines.append(f"\nSEARCH QUERIES: {', '.join(unique_searches)}")

    if titles:
        sample_titles = titles[-40:]
        lines.append(f"\nPAGE TITLES (sample): {'; '.join(sample_titles)}")

    return "\n".join(lines)


def _parse_json_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def summarize_feed_items(items: list[dict]) -> str:
    if not items:
        return ""

    from collections import defaultdict
    by_source: dict = defaultdict(list)
    for item in items:
        by_source[item["source"]].append(item)

    lines = []

    if by_source.get("x"):
        tweets = [i["content"][:200] for i in by_source["x"][:30]]
        lines.append(f"\nX/TWITTER FEED (recent tweets consumed):\n" + "\n".join(f"  - {t}" for t in tweets))

    if by_source.get("linkedin"):
        posts = [i["content"][:200] for i in by_source["linkedin"][:20]]
        lines.append(f"\nLINKEDIN FEED (recent posts consumed):\n" + "\n".join(f"  - {p}" for p in posts))

    if by_source.get("youtube"):
        videos = [f"{i['content']} (by {i['author']})" for i in by_source["youtube"][:25] if i.get("author")]
        if not videos:
            videos = [i["content"][:150] for i in by_source["youtube"][:25]]
        lines.append(f"\nYOUTUBE (watched/recommended):\n" + "\n".join(f"  - {v}" for v in videos))

    if by_source.get("github"):
        commits = [i["content"][:200] for i in by_source["github"] if i["content_type"] == "commit"][:20]
        stars   = [i["content"][:200] for i in by_source["github"] if i["content_type"] == "star"][:15]
        if commits:
            lines.append(f"\nGITHUB COMMITS:\n" + "\n".join(f"  - {c}" for c in commits))
        if stars:
            lines.append(f"\nGITHUB STARRED REPOS:\n" + "\n".join(f"  - {s}" for s in stars))

    if by_source.get("google"):
        searches = [i["content"][:300] for i in by_source["google"][:20]]
        lines.append(f"\nGOOGLE SEARCH RESULTS SEEN:\n" + "\n".join(f"  - {s}" for s in searches))

    # LLM prompts — highest-signal data: exactly what the user is working on
    llm_sources = {"chatgpt", "claude", "perplexity", "opencode", "cursor",
                   "gemini", "grok", "github_copilot", "llm",
                   "claude_code", "ollama", "aider", "sgpt"}
    llm_items = [i for i in items if i["source"] in llm_sources]
    if llm_items:
        by_llm: dict = defaultdict(list)
        for item in llm_items:
            by_llm[item["source"]].append(item["content"][:400])
        llm_lines = []
        for src, prompts in by_llm.items():
            for p in prompts[:15]:
                llm_lines.append(f"  [{src.upper()}] {p}")
        lines.append(f"\nLLM PROMPTS (what user is actively working on / asking AI):\n"
                     + "\n".join(llm_lines[:40]))

    return "\n".join(lines)


def extract_persona() -> dict:
    create_tables()
    events = get_events_last_n_days(7)
    feed_items = get_feed_items_last_n_days(7)

    if not events and not feed_items:
        logger.info("No events found — skipping persona extraction")
        return {}

    summary = summarize_events(events)
    feed_summary = summarize_feed_items(feed_items)
    client = Anthropic()

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=2048,
        system=(
            "You are a behavioral analyst. Extract a structured personality profile "
            "from browsing activity. Be specific and factual. "
            "No speculation beyond what the data shows. "
            "Return ONLY valid JSON — no explanation, no markdown, no preamble."
        ),
        messages=[
            {
                "role": "user",
                "content": (
                    f"Here is 7 days of data for one person:\n\n{summary}\n\n{feed_summary}\n\n"
                    f"Return a JSON object with this exact structure:\n"
                    f"{json.dumps(PERSONA_SCHEMA, indent=2)}\n\n"
                    f"Rules:\n"
                    f"- Fill every field based on evidence in the data\n"
                    f"- active_hours: infer from which hours had most activity\n"
                    f"- updated_at: use ISO-8601 timestamp for right now\n"
                    f"- event_count: {len(events)} browsing events, {len(feed_items)} social/github items\n"
                    f"- Return ONLY the JSON object"
                ),
            }
        ],
    )

    persona = _parse_json_response(response.content[0].text)

    DATA_DIR.mkdir(exist_ok=True)
    PERSONA_FILE.write_text(json.dumps(persona, indent=2))
    save_persona(persona)

    logger.info("Persona written to %s", PERSONA_FILE)
    return persona


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = extract_persona()
    if result:
        print(json.dumps(result, indent=2))
    else:
        print("No events yet — browse for a while first")
