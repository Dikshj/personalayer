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

from database import create_tables, insert_event
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
