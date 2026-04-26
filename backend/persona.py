# backend/persona.py
import json
import logging
from collections import Counter
from pathlib import Path
from typing import Optional

from anthropic import Anthropic
from dotenv import load_dotenv

from database import get_events_last_n_days, save_persona

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


def extract_persona() -> dict:
    events = get_events_last_n_days(7)
    if not events:
        logger.info("No events found — skipping persona extraction")
        return {}

    summary = summarize_events(events)
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
                    f"Here is 7 days of browsing activity for one person:\n\n{summary}\n\n"
                    f"Return a JSON object with this exact structure:\n"
                    f"{json.dumps(PERSONA_SCHEMA, indent=2)}\n\n"
                    f"Rules:\n"
                    f"- Fill every field based on evidence in the data\n"
                    f"- active_hours: infer from which hours had most activity\n"
                    f"- updated_at: use ISO-8601 timestamp for right now\n"
                    f"- event_count: {len(events)}\n"
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
