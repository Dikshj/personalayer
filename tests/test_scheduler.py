import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


def test_contextlayer_has_only_one_3am_scheduler_job():
    from apscheduler.triggers.cron import CronTrigger
    from scheduler import create_scheduler

    scheduler = create_scheduler()
    jobs = {job.id: job for job in scheduler.get_jobs()}
    contextlayer_jobs = sorted(job_id for job_id in jobs if job_id.startswith("contextlayer_"))
    daily_trigger = jobs["contextlayer_daily_refresh"].trigger

    assert contextlayer_jobs == ["contextlayer_daily_refresh"]
    assert isinstance(daily_trigger, CronTrigger)
    assert str(daily_trigger.fields[5]) == "3"
    assert str(daily_trigger.fields[6]) == "0"
