from __future__ import annotations

import time
from typing import Optional

from pcl.persona_diffs import propose_memory_diff


SUPPORTED_MESSAGE_SOURCES = {"whatsapp", "telegram", "slack", "discord", "sms"}


def ingest_messaging_event(
    source: str,
    user_id: str,
    sender: str,
    text: str,
    thread_id: str = "",
    timestamp: Optional[int] = None,
) -> dict:
    source = normalize_message_source(source)
    clean_sender = (sender or "unknown").strip()[:160]
    clean_text = (text or "").strip()
    if not clean_text:
        return {"status": "error", "error": "message_required"}
    timestamp = timestamp or int(time.time() * 1000)

    daily = propose_memory_diff(
        user_id=user_id,
        scope="daily-log",
        proposed_content=(
            f"{source} message from {clean_sender}: "
            f"{_compact_message(clean_text)}"
        ),
        reason=f"Message bridge ingest from {source}",
        source=source,
    )
    people = propose_memory_diff(
        user_id=user_id,
        scope="people",
        proposed_content=(
            f"{clean_sender} appeared in {source}"
            f"{f' thread {thread_id}' if thread_id else ''}."
        ),
        reason=f"Message participant observed from {source}",
        source=source,
    )
    return {
        "status": "ingested",
        "source": source,
        "user_id": user_id,
        "sender": clean_sender,
        "thread_id": thread_id,
        "timestamp": timestamp,
        "memory_updates": [daily, people],
    }


def normalize_message_source(source: str) -> str:
    normalized = (source or "").strip().lower()
    if normalized not in SUPPORTED_MESSAGE_SOURCES:
        raise ValueError("unsupported_message_source")
    return normalized


def _compact_message(text: str) -> str:
    one_line = " ".join(text.split())
    return one_line[:500]
