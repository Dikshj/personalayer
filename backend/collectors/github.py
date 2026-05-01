"""
collectors/github.py

Fetches GitHub activity for a user and stores it as feed_items.
Uses public GitHub API — no auth required for public profiles.
With a token (GITHUB_TOKEN env var) rate limit goes 60 → 5000 req/hr.

Signals extracted:
  - Push events → commit messages (writing style, tech focus)
  - WatchEvents (starred repos) → interests, tools
  - PR review comments → communication style
  - Issues opened → problems being solved
  - Forks → repos user cares about

Run manually:
  python -m collectors.github --username <github_username>

Or trigger via API:
  POST /github/sync  {"username": "elie222"}
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# Allow running standalone (python collectors/github.py)
sys.path.insert(0, str(Path(__file__).parent.parent))
from database import insert_feed_item  # noqa: E402

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def _headers() -> dict:
    token = os.getenv("GITHUB_TOKEN", "")
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _ts(iso: str) -> int:
    """ISO-8601 → milliseconds epoch."""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except Exception:
        return int(time.time() * 1000)


def _fetch_events(username: str) -> list[dict]:
    url = f"{GITHUB_API}/users/{username}/events?per_page=100"
    try:
        res = requests.get(url, headers=_headers(), timeout=10)
        res.raise_for_status()
        return res.json()
    except Exception as exc:
        logger.warning("GitHub events fetch failed: %s", exc)
        return []


def _fetch_starred(username: str) -> list[dict]:
    """Recent repos the user starred."""
    url = f"{GITHUB_API}/users/{username}/starred?per_page=30&sort=created"
    try:
        res = requests.get(url, headers=_headers(), timeout=10)
        res.raise_for_status()
        return res.json()
    except Exception as exc:
        logger.warning("GitHub starred fetch failed: %s", exc)
        return []


def collect_github(username: str) -> int:
    """Fetch GitHub activity + starred repos, store as feed_items. Returns count saved."""
    if not username:
        raise ValueError("username is required")

    saved = 0
    events = _fetch_events(username)

    for event in events:
        etype = event.get("type", "")
        repo = event.get("repo", {}).get("name", "")
        repo_url = f"https://github.com/{repo}"
        ts = _ts(event.get("created_at", ""))

        if etype == "PushEvent":
            commits = event.get("payload", {}).get("commits", [])
            for commit in commits:
                msg = commit.get("message", "").strip()
                if not msg:
                    continue
                insert_feed_item(
                    source="github",
                    content_type="commit",
                    content=f"[{repo}] {msg}",
                    author=username,
                    url=repo_url,
                    timestamp=ts,
                )
                saved += 1

        elif etype == "WatchEvent":  # starred a repo
            desc = event.get("repo", {}).get("description", "") or ""
            insert_feed_item(
                source="github",
                content_type="star",
                content=f"Starred {repo}: {desc}".strip(),
                author=username,
                url=repo_url,
                timestamp=ts,
            )
            saved += 1

        elif etype == "IssuesEvent":
            action = event.get("payload", {}).get("action", "")
            if action != "opened":
                continue
            issue = event.get("payload", {}).get("issue", {})
            title = issue.get("title", "")
            body = (issue.get("body", "") or "")[:300]
            if not title:
                continue
            insert_feed_item(
                source="github",
                content_type="issue",
                content=f"[{repo}] Issue: {title}\n{body}".strip(),
                author=username,
                url=issue.get("html_url", repo_url),
                timestamp=ts,
            )
            saved += 1

        elif etype == "PullRequestReviewCommentEvent":
            body = event.get("payload", {}).get("comment", {}).get("body", "")
            if not body or len(body) < 10:
                continue
            insert_feed_item(
                source="github",
                content_type="pr_review",
                content=f"[{repo}] PR review: {body[:400]}",
                author=username,
                url=repo_url,
                timestamp=ts,
            )
            saved += 1

        elif etype == "ForkEvent":
            forkee = event.get("payload", {}).get("forkee", {})
            desc = forkee.get("description", "") or ""
            insert_feed_item(
                source="github",
                content_type="fork",
                content=f"Forked {repo}: {desc}".strip(),
                author=username,
                url=repo_url,
                timestamp=ts,
            )
            saved += 1

    # Also capture recently starred repos (separate endpoint, richer data)
    starred = _fetch_starred(username)
    for repo in starred:
        name = repo.get("full_name", "")
        desc = repo.get("description", "") or ""
        topics = ", ".join(repo.get("topics", []))
        lang = repo.get("language", "") or ""
        content = f"Starred {name}"
        if desc:
            content += f": {desc}"
        if topics:
            content += f" [topics: {topics}]"
        if lang:
            content += f" [{lang}]"

        insert_feed_item(
            source="github",
            content_type="star",
            content=content,
            author=username,
            url=repo.get("html_url", ""),
            timestamp=int(time.time() * 1000),
        )
        saved += 1

    logger.info("GitHub sync for @%s — %d items saved", username, saved)
    return saved


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Sync GitHub activity to PersonaLayer")
    parser.add_argument("--username", required=True, help="GitHub username")
    args = parser.parse_args()
    count = collect_github(args.username)
    print(f"Saved {count} GitHub items for @{args.username}")
