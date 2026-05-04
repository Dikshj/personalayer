"""
collectors/claude_code_watcher.py

Watches ~/.claude/projects/**/*.jsonl for new Claude Code sessions.
Extracts user prompts (queue-operation / enqueue entries) and sends
them to PersonaLayer as feed_items.

Claude Code session format:
  {"type":"queue-operation","operation":"enqueue","content":"user prompt","timestamp":"..."}

Run as a background daemon:
  python -m collectors.claude_code_watcher

Or one-shot import of all existing sessions:
  python -m collectors.claude_code_watcher --import-existing
"""

import json
import sys
import time
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from database import insert_feed_item  # noqa: E402

logger = logging.getLogger(__name__)

CLAUDE_DIR = Path.home() / ".claude" / "projects"
SEEN_FILE  = Path.home() / ".personalayer" / "claude_code_seen.json"


def load_seen() -> dict:
    """Load map of {filepath: last_byte_offset} so we don't re-process."""
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
    Read JSONL from offset, extract user prompts.
    Returns (new_offset, items_saved).
    """
    saved = 0
    offset = from_offset

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

                # User prompt = queue-operation enqueue
                if (entry.get("type") == "queue-operation"
                        and entry.get("operation") == "enqueue"
                        and entry.get("content")):

                    content = str(entry["content"]).strip()
                    if len(content) < 5:
                        continue

                    # Parse timestamp
                    ts_str = entry.get("timestamp", "")
                    try:
                        from datetime import datetime, timezone
                        ts = int(datetime.fromisoformat(
                            ts_str.replace("Z", "+00:00")
                        ).timestamp() * 1000)
                    except Exception:
                        ts = int(time.time() * 1000)

                    insert_feed_item(
                        source="claude_code",
                        content_type="prompt",
                        content=content[:1500],
                        author="user",
                        url=str(filepath),
                        timestamp=ts,
                    )
                    saved += 1

    except (OSError, PermissionError) as exc:
        logger.warning("Cannot read %s: %s", filepath, exc)

    return offset, saved


def scan_all(seen: dict, import_existing: bool = False) -> dict:
    """Scan all JSONL files in ~/.claude/projects/."""
    if not CLAUDE_DIR.exists():
        logger.info("Claude Code directory not found: %s", CLAUDE_DIR)
        return seen

    total = 0
    for jsonl_file in CLAUDE_DIR.rglob("*.jsonl"):
        key = str(jsonl_file)
        from_offset = 0 if import_existing else seen.get(key, 0)
        new_offset, saved = process_jsonl(jsonl_file, from_offset)
        seen[key] = new_offset
        total += saved

    if total:
        logger.info("Claude Code: %d new prompts captured", total)
    return seen


def watch(poll_interval: int = 30) -> None:
    """Continuously watch for new Claude Code prompts."""
    logger.info("Watching Claude Code sessions in %s (poll every %ds)", CLAUDE_DIR, poll_interval)
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
    parser.add_argument("--import-existing", action="store_true",
                        help="Import all existing sessions (not just new lines)")
    parser.add_argument("--watch", action="store_true", default=True,
                        help="Keep watching for new prompts (default)")
    parser.add_argument("--poll", type=int, default=30,
                        help="Poll interval in seconds (default 30)")
    args = parser.parse_args()

    if args.import_existing:
        seen = {}
        seen = scan_all(seen, import_existing=True)
        save_seen(seen)
        print(f"Import done. Processed {len(seen)} session files.")
    else:
        watch(args.poll)
