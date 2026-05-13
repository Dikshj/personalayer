import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


def test_builtin_collector_specs_include_privacy_metadata():
    from collectors.base import builtin_collector_specs

    specs = {spec.source: spec for spec in builtin_collector_specs()}

    assert specs["browser_extension"].raw_content_stored is False
    assert specs["github"].raw_content_stored is True
    assert specs["claude_code"].event_types == ("session_signals",)
    assert specs["ollama"].mode == "proxy"


def test_registry_exposes_scheduled_collector_jobs(monkeypatch):
    from collectors.registry import scheduled_collector_jobs

    monkeypatch.setenv("PERSONALAYER_ENABLED_COLLECTORS", "claude_code,github")
    jobs = {job.id: job for job in scheduled_collector_jobs()}

    assert jobs["daily_claude_code"].collector_source == "claude_code"
    assert (jobs["daily_claude_code"].hour, jobs["daily_claude_code"].minute) == (1, 0)
    assert jobs["daily_github"].collector_source == "github"
    assert (jobs["daily_github"].hour, jobs["daily_github"].minute) == (1, 30)


def test_resident_collectors_are_declared():
    from collectors.registry import builtin_collector_runtimes

    resident_sources = {
        runtime.spec.source
        for runtime in builtin_collector_runtimes()
        if runtime.start is not None
    }

    assert resident_sources == {"ollama", "shell"}


def test_collector_runtimes_wrap_protocol_collectors():
    from collectors.registry import builtin_collector_runtimes

    runtimes = builtin_collector_runtimes()

    assert {runtime.spec.source for runtime in runtimes} == {
        runtime.collector.spec.source for runtime in runtimes
    }
    assert all(hasattr(runtime.collector, "start") for runtime in runtimes)


def test_collector_settings_disable_default_jobs(monkeypatch):
    from collectors.registry import scheduled_collector_jobs

    monkeypatch.setenv("PERSONALAYER_DISABLED_COLLECTORS", "claude_code")

    jobs = {job.id for job in scheduled_collector_jobs()}

    assert "daily_claude_code" not in jobs


def test_collector_settings_enable_opt_in_jobs(monkeypatch):
    from collectors.registry import scheduled_collector_jobs

    monkeypatch.setenv("PERSONALAYER_ENABLED_COLLECTORS", "github")

    jobs = {job.id for job in scheduled_collector_jobs()}

    assert jobs == {"daily_github"}
