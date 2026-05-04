# backend/scheduler.py
import os
import logging
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


# ── 1:00 AM — Claude Code scan ────────────────────────────────────────────────

def run_claude_code_scan() -> None:
    """One-shot scan of all Claude Code sessions. New lines only (incremental)."""
    try:
        from collectors.claude_code_watcher import load_seen, scan_all, save_seen
        seen = load_seen()
        seen = scan_all(seen)
        save_seen(seen)
        logger.info("Claude Code scan complete")
    except Exception as exc:
        logger.error("Claude Code scan failed: %s", exc)


# ── 1:30 AM — GitHub sync ─────────────────────────────────────────────────────

def run_github_sync() -> None:
    username = os.getenv("GITHUB_USERNAME", "").strip()
    if not username:
        return
    try:
        from collectors.github import collect_github
        count = collect_github(username)
        logger.info("GitHub sync @%s: %d items", username, count)
    except Exception as exc:
        logger.error("GitHub sync failed: %s", exc)


# ── 2:00 AM — Persona extraction ──────────────────────────────────────────────

def run_persona_extraction() -> None:
    try:
        from persona import extract_persona
        persona = extract_persona()
        logger.info("Persona extracted: %s keys", list(persona.keys()))
    except Exception as exc:
        logger.error("Persona extraction failed: %s", exc)


# ── Ollama proxy (daemon — passive, zero overhead when Ollama not in use) ──────

def _ollama_proxy_thread() -> None:
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
    except Exception:
        logger.info("Ollama not running — proxy skipped")
        return
    try:
        from collectors.ollama_proxy import PROXY_PORT, ProxyHandler
        from http.server import HTTPServer
        server = HTTPServer(("127.0.0.1", PROXY_PORT), ProxyHandler)
        logger.info("Ollama proxy :11435 → :11434")
        server.serve_forever()
    except OSError:
        logger.info("Ollama proxy port busy — skipping")
    except Exception as exc:
        logger.error("Ollama proxy error: %s", exc)


def start_ollama_proxy() -> None:
    t = threading.Thread(target=_ollama_proxy_thread, daemon=True, name="ollama-proxy")
    t.start()


# ── Shell wrapper one-time install ────────────────────────────────────────────

def ensure_shell_wrappers() -> None:
    try:
        from collectors.shell_wrapper import install_aliases
        install_aliases()
    except Exception as exc:
        logger.warning("Shell wrapper install skipped: %s", exc)


# ── Scheduler factory ─────────────────────────────────────────────────────────

def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()

    # 1:00 AM — collect Claude Code signals
    scheduler.add_job(
        run_claude_code_scan,
        CronTrigger(hour=1, minute=0),
        id="daily_claude_code",
        replace_existing=True,
    )

    # 1:30 AM — sync GitHub
    scheduler.add_job(
        run_github_sync,
        CronTrigger(hour=1, minute=30),
        id="daily_github",
        replace_existing=True,
    )

    # 2:00 AM — extract persona from all collected data
    scheduler.add_job(
        run_persona_extraction,
        CronTrigger(hour=2, minute=0),
        id="daily_persona",
        replace_existing=True,
    )

    return scheduler


def start_background_collectors() -> None:
    """Called once at app startup. Only Ollama proxy runs as daemon (passive)."""
    start_ollama_proxy()
    ensure_shell_wrappers()
