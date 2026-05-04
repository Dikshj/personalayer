# backend/scheduler.py
import os
import logging
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


# ── Persona extraction (nightly 2AM) ──────────────────────────────────────────

def run_persona_extraction() -> None:
    try:
        from persona import extract_persona
        persona = extract_persona()
        logger.info("Persona extracted: %s keys", list(persona.keys()))
    except Exception as exc:
        logger.error("Persona extraction failed: %s", exc)


# ── GitHub sync (every 6 hours) ───────────────────────────────────────────────

def run_github_sync() -> None:
    username = os.getenv("GITHUB_USERNAME", "").strip()
    if not username:
        return  # silently skip — username not configured
    try:
        from collectors.github import collect_github
        count = collect_github(username)
        logger.info("GitHub sync @%s: %d items", username, count)
    except Exception as exc:
        logger.error("GitHub sync failed: %s", exc)


# ── Claude Code watcher (background thread, polls every 30s) ──────────────────

def run_claude_code_watcher() -> None:
    """Runs as a daemon thread — polls ~/.claude/projects/**/*.jsonl for new sessions."""
    try:
        from collectors.claude_code_watcher import watch
        watch(poll_interval=30)
    except Exception as exc:
        logger.error("Claude Code watcher crashed: %s", exc)


def start_claude_code_watcher() -> threading.Thread:
    t = threading.Thread(target=run_claude_code_watcher, daemon=True,
                         name="claude-code-watcher")
    t.start()
    logger.info("Claude Code watcher started (daemon thread)")
    return t


# ── Ollama proxy (background thread, optional) ────────────────────────────────

def run_ollama_proxy() -> None:
    """Start Ollama proxy only if Ollama is actually running on :11434."""
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
    except Exception:
        logger.info("Ollama not detected on :11434 — proxy not started")
        return
    try:
        from collectors.ollama_proxy import PROXY_PORT, ProxyHandler
        from http.server import HTTPServer
        server = HTTPServer(("127.0.0.1", PROXY_PORT), ProxyHandler)
        logger.info("Ollama proxy started on :%d", PROXY_PORT)
        server.serve_forever()
    except OSError:
        logger.info("Ollama proxy port :11435 already in use — skipping")
    except Exception as exc:
        logger.error("Ollama proxy failed: %s", exc)


def start_ollama_proxy() -> threading.Thread:
    t = threading.Thread(target=run_ollama_proxy, daemon=True, name="ollama-proxy")
    t.start()
    return t


# ── Shell wrapper auto-install (one-time) ─────────────────────────────────────

def ensure_shell_wrappers() -> None:
    """Install shell aliases once. Skips if already installed."""
    try:
        from collectors.shell_wrapper import install_aliases
        install_aliases()
    except Exception as exc:
        logger.warning("Shell wrapper install skipped: %s", exc)


# ── Scheduler factory ─────────────────────────────────────────────────────────

def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()

    # Nightly persona extraction — 2AM
    scheduler.add_job(
        run_persona_extraction,
        CronTrigger(hour=2, minute=0),
        id="nightly_persona",
        replace_existing=True,
    )

    # GitHub sync — every 6 hours
    scheduler.add_job(
        run_github_sync,
        IntervalTrigger(hours=6),
        id="github_sync",
        replace_existing=True,
    )

    return scheduler


def start_background_collectors() -> None:
    """Start all long-running collector daemons. Called once at app startup."""
    start_claude_code_watcher()
    start_ollama_proxy()
    ensure_shell_wrappers()
