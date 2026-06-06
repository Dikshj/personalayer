import logging
import os
from dataclasses import dataclass
from typing import Callable

from collectors.base import Collector, CollectorSpec, builtin_collector_specs
from settings import is_collector_enabled

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScheduledCollectorJob:
    id: str
    collector_source: str
    hour: int
    minute: int
    run: Callable[[], None]


@dataclass(frozen=True)
class CollectorRuntime:
    collector: Collector
    spec: CollectorSpec
    start: Callable[[], None] | None = None
    scheduled_jobs: tuple[ScheduledCollectorJob, ...] = ()
    enabled_by_default: bool = False


class BrowserExtensionCollector:
    def __init__(self, spec: CollectorSpec):
        self.spec = spec

    def start(self) -> None:
        return None


class ClaudeCodeCollector:
    def __init__(self, spec: CollectorSpec):
        self.spec = spec

    def start(self) -> None:
        return None

    def scan(self) -> None:
        """One-shot scan of all Claude Code sessions. New lines only."""
        try:
            from collectors.claude_code_watcher import load_seen, scan_all, save_seen
            seen = load_seen()
            seen = scan_all(seen)
            save_seen(seen)
            logger.info("Claude Code scan complete")
        except Exception as exc:
            logger.error("Claude Code scan failed: %s", exc)


class GitHubCollector:
    def __init__(self, spec: CollectorSpec):
        self.spec = spec

    def start(self) -> None:
        return None

    def sync(self) -> None:
        username = os.getenv("GITHUB_USERNAME", "").strip()
        if not username:
            return
        try:
            from collectors.github import collect_github
            count = collect_github(username)
            logger.info("GitHub sync @%s: %d items", username, count)
        except Exception as exc:
            logger.error("GitHub sync failed: %s", exc)


class ShellWrapperCollector:
    def __init__(self, spec: CollectorSpec):
        self.spec = spec

    def start(self) -> None:
        try:
            from collectors.shell_wrapper import install_aliases
            install_aliases()
        except Exception as exc:
            logger.warning("Shell wrapper install skipped: %s", exc)


class PCLIntegrationCollector:
    def __init__(self, spec: CollectorSpec):
        self.spec = spec

    def start(self) -> None:
        return None

    def sync(self) -> None:
        try:
            from pcl.integration_jobs import sync_integration
            result = sync_integration(self.spec.source)
            status = result.get("status", "unknown") if isinstance(result, dict) else "unknown"
            if status == "error":
                logger.warning("PCL integration sync %s failed: %s", self.spec.source, result)
            else:
                logger.info("PCL integration sync %s complete: %s", self.spec.source, result)
        except Exception as exc:
            logger.error("PCL integration sync %s failed: %s", self.spec.source, exc)


def run_claude_code_scan() -> None:
    collector = ClaudeCodeCollector(_spec_by_source()["claude_code"])
    collector.scan()


def run_github_sync() -> None:
    collector = GitHubCollector(_spec_by_source()["github"])
    collector.sync()


def ensure_shell_wrappers() -> None:
    collector = ShellWrapperCollector(_spec_by_source()["shell"])
    collector.start()


def _spec_by_source() -> dict[str, CollectorSpec]:
    return {spec.source: spec for spec in builtin_collector_specs()}


def builtin_collector_runtimes() -> list[CollectorRuntime]:
    specs = _spec_by_source()
    browser = BrowserExtensionCollector(specs["browser_extension"])
    claude_code = ClaudeCodeCollector(specs["claude_code"])
    shell = ShellWrapperCollector(specs["shell"])
    github = GitHubCollector(specs["github"])
    pcl_integration_sources = (
        "gmail",
        "calendar",
        "notion",
        "google_drive",
        "youtube",
        "spotify",
        "apple_health",
        "linkedin",
        "x",
        "instagram",
        "chatgpt",
        "claude",
        "perplexity",
        "opencode",
        "cursor",
        "gemini",
        "grok",
        "github_copilot",
        "aider",
        "terminal",
        "vscode",
        "ide",
    )

    runtimes = [
        CollectorRuntime(
            collector=browser,
            spec=browser.spec,
            enabled_by_default=browser.spec.enabled_by_default,
        ),
        CollectorRuntime(
            collector=claude_code,
            spec=claude_code.spec,
            enabled_by_default=claude_code.spec.enabled_by_default,
            scheduled_jobs=(
                ScheduledCollectorJob(
                    id="daily_claude_code",
                    collector_source="claude_code",
                    hour=1,
                    minute=0,
                    run=claude_code.scan,
                ),
            ),
        ),
        CollectorRuntime(
            collector=shell,
            spec=shell.spec,
            start=shell.start,
            enabled_by_default=shell.spec.enabled_by_default,
        ),
        CollectorRuntime(
            collector=github,
            spec=github.spec,
            enabled_by_default=github.spec.enabled_by_default,
            scheduled_jobs=(
                ScheduledCollectorJob(
                    id="daily_github",
                    collector_source="github",
                    hour=1,
                    minute=30,
                    run=github.sync,
                ),
            ),
        ),
    ]

    for index, source in enumerate(pcl_integration_sources):
        collector = PCLIntegrationCollector(specs[source])
        runtimes.append(
            CollectorRuntime(
                collector=collector,
                spec=collector.spec,
                enabled_by_default=collector.spec.enabled_by_default,
                scheduled_jobs=(
                    ScheduledCollectorJob(
                        id=f"daily_{source}",
                        collector_source=source,
                        hour=index % 24,
                        minute=(index * 7) % 60,
                        run=collector.sync,
                    ),
                ),
            )
        )

    return runtimes


def scheduled_collector_jobs() -> list[ScheduledCollectorJob]:
    jobs: list[ScheduledCollectorJob] = []
    for runtime in builtin_collector_runtimes():
        if not is_collector_enabled(runtime.spec.source, runtime.enabled_by_default):
            continue
        jobs.extend(runtime.scheduled_jobs)
    return jobs


def start_resident_collectors() -> None:
    for runtime in builtin_collector_runtimes():
        if runtime.start and is_collector_enabled(runtime.spec.source, runtime.enabled_by_default):
            runtime.start()
