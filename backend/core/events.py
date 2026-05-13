from dataclasses import dataclass
from typing import Literal


EventSource = Literal["browser", "feed", "shell", "ide", "llm", "github", "system"]


@dataclass(frozen=True)
class BrowserActivityEvent:
    url: str
    title: str = ""
    time_spent_seconds: int = 0
    timestamp: int = 0


@dataclass(frozen=True)
class FeedActivityEvent:
    source: str
    content_type: str
    content: str
    author: str = ""
    url: str = ""
    timestamp: int = 0


@dataclass(frozen=True)
class IngestionResult:
    status: str
    source: EventSource
    reason: str = ""

