# backend/scheduler.py
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


def run_persona_extraction() -> None:
    try:
        from persona import extract_persona
        persona = extract_persona()
        logger.info("Persona extracted: %s keys", list(persona.keys()))
    except Exception as exc:
        logger.error("Persona extraction failed: %s", exc)


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_persona_extraction,
        CronTrigger(hour=2, minute=0),
        id="nightly_persona",
        replace_existing=True,
    )
    return scheduler
