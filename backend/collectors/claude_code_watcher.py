"""
collectors/claude_code_watcher.py

Watches ~/.claude/projects/**/*.jsonl for Claude Code sessions.
Extracts MINIMAL signals only — tech stack, task type, domain.
Raw prompt text is NEVER stored.

What gets stored per session:
  "[claude_code] task:building | domain:ai_ml | langs:python | tools:fastapi,sqlite"

Run:
  python -m collectors.claude_code_watcher --import-existing
  python -m collectors.claude_code_watcher   (watch mode, polls every 30s)
"""

import json
import sys
import time
import argparse
import logging
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))
from database import insert_feed_item  # noqa: E402
from collectors.signal_extractor import extract_signals, signals_to_content  # noqa: E402

logger = logging.getLogger(__name__)

CLAUDE_DIR = Path.home() / ".claude" / "projects"
SEEN_FILE  = Path.home() / ".personalayer" / "claude_code_seen.json"


def load_seen() -> dict:
    if SEEN_FILE.exists():
        try:
            return json.loads(SEEN_FILE.read_text())
        except Exception:
            pass
    return {}


def save_seen(seen: dict) -> None:
    SEEN_FILE.parent.mkdir(exist_ok=True)
    SEEN_FILE.write_text(json.dumps(seen))


def process_jsonl(filepath: Path, from_offset: int = 0) -> tuple[int, int]:
    """
    Read JSONL from offset. Accumulate signals per session.
    Store ONE aggregated signal record per session, not one per prompt.
    """
    saved = 0
    offset = from_offset

    # Accumulate all text in this batch to extract combined signals
    all_text_parts: list[str] = []
    timestamps: list[int] = []

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(offset)
            for line in f:
                offset += len(line.encode("utf-8"))
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if (entry.get("type") == "queue-operation"
                        and entry.get("operation") == "enqueue"
                        and entry.get("content")):

                    # Add raw text only for local signal extraction
                    # It is NEVER written to disk or sent anywhere
                    raw = str(entry["content"])
                    all_text_parts.append(raw)

                    ts_str = entry.get("timestamp", "")
                    try:
                        from datetime import datetime
                        ts = int(datetime.fromisoformat(
                            ts_str.replace("Z", "+00:00")
                        ).timestamp() * 1000)
                        timestamps.append(ts)
                    except Exception:
                        timestamps.append(int(time.time() * 1000))

    except (OSError, PermissionError) as exc:
        logger.warning("Cannot read %s: %s", filepath, exc)
        return from_offset, 0

    if not all_text_parts:
        return offset, 0

    # Extract signals from combined session text — raw text discarded after this
    combined = " ".join(all_text_parts)
    signals = extract_signals(combined)
    content = signals_to_content(signals, "claude_code")

    if content:
        # Add session metadata (not prompt content)
        content += f" | prompts:{len(all_text_parts)}"
        ts = timestamps[0] if timestamps else int(time.time() * 1000)

        insert_feed_item(
            source="claude_code",
            content_type="session_signals",
            content=content,
            author="user",
            url=str(filepath.name),   # just filename, not full path
            timestamp=ts,
        )
        saved = 1
        logger.info("Captured Claude Code session signals: %s", content)

    return offset, saved


def scan_all(seen: dict, import_existing: bool = False) -> dict:
    if not CLAUDE_DIR.exists():
        return seen

    total = 0
    for jsonl_file in CLAUDE_DIR.rglob("*.jsonl"):
        key = str(jsonl_file)
        from_offset = 0 if import_existing else seen.get(key, 0)
        new_offset, saved = process_jsonl(jsonl_file, from_offset)
        seen[key] = new_offset
        total += saved

    if total:
        logger.info("Claude Code: %d session signal records saved", total)
    return seen


def watch(poll_interval: int = 30) -> None:
    logger.info("Watching Claude Code sessions (poll every %ds)", poll_interval)
    seen = load_seen()
    while True:
        try:
            seen = scan_all(seen)
            save_seen(seen)
        except Exception as exc:
            logger.error("Scan error: %s", exc)
        time.sleep(poll_interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [claude_code] %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--import-existing", action="store_true")
    parser.add_argument("--poll", type=int, default=30)
    args = parser.parse_args()

    if args.import_existing:
        seen = scan_all({}, import_existing=True)
        save_seen(seen)
        print(f"Done. Processed {len(seen)} session files.")
    else:
        watch(args.poll)
