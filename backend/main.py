# backend/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from urllib.parse import urlparse, parse_qs
import uvicorn
from pathlib import Path

from database import create_tables, insert_event, add_to_waitlist, get_waitlist_count, insert_feed_item
from scheduler import create_scheduler


SKIP_PATTERNS = ("localhost", "127.0.0.1", "chrome://", "chrome-extension://", "about:")


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    scheduler = create_scheduler()
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="PersonaLayer", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["chrome-extension://*", "http://localhost:*"],
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)

DASHBOARD_DIR = Path(__file__).parent.parent / "dashboard"
if DASHBOARD_DIR.exists():
    app.mount("/dashboard", StaticFiles(directory=str(DASHBOARD_DIR), html=True), name="dashboard")

LANDING_DIR = Path(__file__).parent.parent / "landing"
if LANDING_DIR.exists():
    app.mount("/landing", StaticFiles(directory=str(LANDING_DIR), html=True), name="landing")


class WaitlistEntry(BaseModel):
    email: str
    source: Optional[str] = "landing"


@app.post("/waitlist")
async def join_waitlist(entry: WaitlistEntry):
    if "@" not in entry.email or "." not in entry.email:
        return {"status": "error", "error": "Invalid email"}
    added = add_to_waitlist(entry.email, entry.source or "landing")
    return {
        "status": "ok" if added else "already_joined",
        "count": get_waitlist_count(),
    }


@app.get("/waitlist/count")
async def waitlist_count():
    return {"count": get_waitlist_count()}


class BrowsingEvent(BaseModel):
    url: str
    title: Optional[str] = ""
    time_spent_seconds: Optional[int] = 0
    timestamp: int


def extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def extract_search_query(url: str) -> Optional[str]:
    try:
        params = parse_qs(urlparse(url).query)
        for key in ("q", "query", "search", "s", "k"):
            if key in params:
                return params[key][0]
    except Exception:
        pass
    return None


@app.post("/event")
async def receive_event(event: BrowsingEvent):
    if any(p in event.url for p in SKIP_PATTERNS):
        return {"status": "skipped"}

    insert_event(
        url=event.url,
        title=event.title or "",
        domain=extract_domain(event.url),
        time_spent_seconds=event.time_spent_seconds or 0,
        search_query=extract_search_query(event.url),
        timestamp=event.timestamp,
    )
    return {"status": "ok"}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "personalayer"}


@app.get("/persona")
async def get_persona_endpoint():
    from database import get_latest_persona
    persona = get_latest_persona()
    if not persona:
        return {"error": "No persona yet. Browse for 24h or run: python persona.py"}
    return persona


class FeedEvent(BaseModel):
    source: str          # "x", "linkedin", "youtube", "google", "github"
    content_type: str    # "tweet", "post", "watch", "recommended", "search_results", "commit"
    content: str
    author: Optional[str] = ""
    url: Optional[str] = ""
    timestamp: int


ALLOWED_SOURCES = {"x", "linkedin", "youtube", "google", "github"}


@app.post("/feed-event")
async def receive_feed_event(event: FeedEvent):
    if event.source not in ALLOWED_SOURCES:
        return {"status": "error", "error": "unknown source"}
    if not event.content.strip():
        return {"status": "skipped"}
    insert_feed_item(
        source=event.source,
        content_type=event.content_type,
        content=event.content.strip(),
        author=event.author or "",
        url=event.url or "",
        timestamp=event.timestamp,
    )
    return {"status": "ok"}


@app.post("/github/sync")
async def sync_github(payload: dict):
    username = payload.get("username", "").strip()
    if not username:
        return {"status": "error", "error": "username required"}
    try:
        from collectors.github import collect_github
        count = collect_github(username)
        return {"status": "ok", "items_saved": count}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@app.post("/extract")
async def trigger_extraction():
    from persona import extract_persona
    try:
        persona = extract_persona()
        if persona:
            return {"status": "ok"}
        return {"status": "error", "error": "No events to analyze"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=7823)
