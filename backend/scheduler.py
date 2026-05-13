# backend/scheduler.py
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from collectors.registry import (
    run_claude_code_scan,
    run_github_sync,
    scheduled_collector_jobs,
    start_resident_collectors,
)

logger = logging.getLogger(__name__)


def run_persona_extraction() -> None:
    try:
        from persona import extract_persona
        persona = extract_persona()
        logger.info("Persona extracted: %s keys", list(persona.keys()))
    except Exception as exc:
        logger.error("Persona extraction failed: %s", exc)


def refresh_living_persona() -> None:
    """Cheap local aggregation of derived signals. Raw data never leaves the device."""
    try:
        from living_persona import build_living_persona
        living = build_living_persona()
        logger.info("Living persona refreshed: %d signals", living["meta"]["signal_count"])
    except Exception as exc:
        logger.error("Living persona refresh failed: %s", exc)


def run_contextlayer_synthesis_cycle() -> None:
    try:
        from pcl.contextlayer import run_inductive_memory_job, run_profile_synthesizer
        synth = run_profile_synthesizer()
        inductive = run_inductive_memory_job()
        logger.info("ContextLayer synthesis: %s, inductive: %s", synth, inductive)
    except Exception as exc:
        logger.error("ContextLayer synthesis failed: %s", exc)


def run_contextlayer_reflection_cycle() -> None:
    try:
        from pcl.contextlayer import run_decay_engine, run_reflective_memory_job
        decay = run_decay_engine()
        reflective = run_reflective_memory_job()
        logger.info("ContextLayer decay: %s, reflective: %s", decay, reflective)
    except Exception as exc:
        logger.error("ContextLayer reflection failed: %s", exc)


def run_contextlayer_daily_refresh_cycle() -> None:
    try:
        from pcl.daily_refresh import run_due_daily_refreshes

        result = run_due_daily_refreshes()
        logger.info(
            "ContextLayer daily refresh due users: %d",
            result["refreshed"],
        )
    except Exception as exc:
        logger.error("ContextLayer daily refresh failed: %s", exc)


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()

    for job in scheduled_collector_jobs():
        scheduler.add_job(
            job.run,
            CronTrigger(hour=job.hour, minute=job.minute),
            id=job.id,
            replace_existing=True,
        )

    scheduler.add_job(
        run_persona_extraction,
        CronTrigger(hour=2, minute=0),
        id="daily_persona",
        replace_existing=True,
    )

    scheduler.add_job(
        refresh_living_persona,
        IntervalTrigger(minutes=15),
        id="living_persona_refresh",
        replace_existing=True,
    )

    scheduler.add_job(
        run_contextlayer_synthesis_cycle,
        IntervalTrigger(hours=6),
        id="contextlayer_synthesis",
        replace_existing=True,
    )

    scheduler.add_job(
        run_contextlayer_reflection_cycle,
        CronTrigger(hour=3, minute=0),
        id="contextlayer_reflection",
        replace_existing=True,
    )

    scheduler.add_job(
        run_contextlayer_daily_refresh_cycle,
        CronTrigger(hour=3, minute=0),
        id="contextlayer_daily_refresh",
        replace_existing=True,
    )

    return scheduler


def start_background_collectors() -> None:
    """Called once at app startup for resident collector runtimes."""
    start_resident_collectors()
