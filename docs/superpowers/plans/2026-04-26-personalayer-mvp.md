# PersonaLayer MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-first Chrome extension + Python backend + MCP server that captures browsing behavior, extracts a personality profile via Claude API, and exposes it to Claude Desktop and Cursor in 5 days.

**Architecture:** Chrome extension sends tab events to a local FastAPI server (localhost:7823) which stores them in SQLite. A nightly job calls the Claude API to extract a persona JSON from the last 7 days of activity. An MCP server reads that persona and exposes 3 tools to any MCP client.

**Tech Stack:** Python 3.11+, FastAPI 0.115, SQLite (stdlib), Anthropic SDK 0.40, MCP SDK 1.3, APScheduler 3.10, Chrome Extension Manifest V3, Vanilla JS

---

## File Map

```
personalayer/
├── extension/
│   ├── manifest.json          # MV3 config — permissions, background, content scripts
│   ├── background.js          # Service worker — tab tracking, sends events to FastAPI
│   ├── content.js             # Stub for v1 (page-level events for v2)
│   └── icons/
│       └── icon128.png        # Placeholder icon (any 128x128 PNG)
│
├── backend/
│   ├── database.py            # SQLite: create_tables, insert_event, get_events, save_persona
│   ├── main.py                # FastAPI: POST /event, GET /health, scheduler startup
│   ├── persona.py             # Claude API: summarize_events, extract_persona
│   ├── mcp_server.py          # MCP: get_persona, get_context, get_current_focus
│   ├── scheduler.py           # APScheduler: nightly 2am persona extraction job
│   ├── requirements.txt       # All Python deps pinned
│   └── .env.example           # ANTHROPIC_API_KEY=
│
├── dashboard/
│   ├── index.html             # View + edit persona, served by FastAPI
│   └── style.css              # Minimal dark styles
│
├── tests/
│   ├── test_database.py       # Unit tests for all database.py functions
│   ├── test_persona.py        # Unit tests for summarize_events (Claude mocked)
│   └── test_mcp.py            # Unit tests for MCP tool return values
│
├── install.sh                 # Mac: pip install, .env scaffold, config gen
├── install.bat                # Windows: same
└── claude_desktop_config.json.template   # Drop-in MCP config snippet
```

---

## Task 1: Project Setup + Dependencies

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create requirements.txt**

```
# backend/requirements.txt
fastapi==0.115.5
uvicorn==0.32.0
anthropic==0.40.0
mcp==1.3.0
apscheduler==3.10.4
python-dotenv==1.0.1
pydantic==2.10.0
pytest==8.3.0
pytest-asyncio==0.24.0
httpx==0.27.0
```

- [ ] **Step 1b: Create pytest.ini (required for async tests)**

```ini
# pytest.ini  (place in project root: personalayer/pytest.ini)
[pytest]
asyncio_mode = auto
testpaths = tests
```

- [ ] **Step 2: Create .env.example**

```
# backend/.env.example
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

- [ ] **Step 3: Create empty test init**

```python
# tests/__init__.py
```

- [ ] **Step 4: Install dependencies**

```bash
cd backend
pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt backend/.env.example tests/__init__.py
git commit -m "feat: add project dependencies and test scaffold"
```

---

## Task 2: Database Layer

**Files:**
- Create: `backend/database.py`
- Create: `tests/test_database.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_database.py
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import tempfile
from pathlib import Path
from unittest.mock import patch

# Point DB to temp dir for tests
TEST_DIR = Path(tempfile.mkdtemp())

@pytest.fixture(autouse=True)
def use_test_db(monkeypatch):
    import database
    monkeypatch.setattr(database, 'DATA_DIR', TEST_DIR)
    monkeypatch.setattr(database, 'DB_PATH', TEST_DIR / 'test.db')
    database.create_tables()
    yield
    db_file = TEST_DIR / 'test.db'
    if db_file.exists():
        db_file.unlink()

def test_create_tables_is_idempotent():
    from database import create_tables
    create_tables()  # second call should not raise
    create_tables()  # third call should not raise

def test_insert_and_retrieve_event():
    from database import insert_event, get_events_last_n_days
    import time
    now_ms = int(time.time() * 1000)
    insert_event(
        url="https://github.com/anthropics/anthropic-sdk-python",
        title="Anthropic SDK Python",
        domain="github.com",
        time_spent_seconds=120,
        search_query=None,
        timestamp=now_ms
    )
    events = get_events_last_n_days(7)
    assert len(events) == 1
    assert events[0]['domain'] == 'github.com'
    assert events[0]['time_spent_seconds'] == 120

def test_search_query_stored():
    from database import insert_event, get_events_last_n_days
    import time
    insert_event(
        url="https://google.com/search?q=mcp+server+python",
        title="mcp server python - Google Search",
        domain="google.com",
        time_spent_seconds=10,
        search_query="mcp server python",
        timestamp=int(time.time() * 1000)
    )
    events = get_events_last_n_days(1)
    assert events[0]['search_query'] == 'mcp server python'

def test_old_events_excluded():
    from database import insert_event, get_events_last_n_days
    old_ts = int((__import__('datetime').datetime.now() - __import__('datetime').timedelta(days=10)).timestamp() * 1000)
    insert_event("https://old.com", "Old", "old.com", 10, None, old_ts)
    events = get_events_last_n_days(7)
    assert len(events) == 0

def test_save_and_get_persona():
    from database import save_persona, get_latest_persona
    persona = {"identity": {"role": "developer"}, "meta": {"event_count": 42}}
    save_persona(persona)
    result = get_latest_persona()
    assert result['identity']['role'] == 'developer'
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /path/to/personalayer
pytest tests/test_database.py -v
```

Expected: `ModuleNotFoundError: No module named 'database'` or similar import error.

- [ ] **Step 3: Implement database.py**

```python
# backend/database.py
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

DATA_DIR = Path.home() / ".personalayer"
DB_PATH = DATA_DIR / "data.db"


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables() -> None:
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                title TEXT DEFAULT '',
                domain TEXT DEFAULT '',
                time_spent_seconds INTEGER DEFAULT 0,
                search_query TEXT,
                timestamp INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS persona_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def insert_event(
    url: str,
    title: str,
    domain: str,
    time_spent_seconds: int,
    search_query: Optional[str],
    timestamp: int,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO events
               (url, title, domain, time_spent_seconds, search_query, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (url, title, domain, time_spent_seconds, search_query, timestamp),
        )
        conn.commit()


def get_events_last_n_days(n: int) -> list[dict]:
    cutoff_ms = int((datetime.now() - timedelta(days=n)).timestamp() * 1000)
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM events WHERE timestamp >= ? ORDER BY timestamp DESC",
            (cutoff_ms,),
        ).fetchall()
    return [dict(row) for row in rows]


def save_persona(persona: dict) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO persona_history (data) VALUES (?)",
            (json.dumps(persona),),
        )
        conn.commit()


def get_latest_persona() -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT data FROM persona_history ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    if row:
        return json.loads(row["data"])
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_database.py -v
```

Expected output:
```
test_database.py::test_create_tables_is_idempotent PASSED
test_database.py::test_insert_and_retrieve_event PASSED
test_database.py::test_search_query_stored PASSED
test_database.py::test_old_events_excluded PASSED
test_database.py::test_save_and_get_persona PASSED
5 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/database.py tests/test_database.py
git commit -m "feat: add SQLite database layer with events and persona tables"
```

---

## Task 3: FastAPI Event Receiver

**Files:**
- Create: `backend/main.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_main.py
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

TEST_DIR = Path(tempfile.mkdtemp())

@pytest.fixture(autouse=True)
def use_test_db(monkeypatch):
    import database
    monkeypatch.setattr(database, 'DATA_DIR', TEST_DIR)
    monkeypatch.setattr(database, 'DB_PATH', TEST_DIR / 'test_main.db')
    database.create_tables()
    # Prevent real APScheduler from starting in tests
    monkeypatch.setattr('main.create_scheduler', lambda: MagicMock(start=lambda: None, shutdown=lambda: None))

@pytest.fixture
def client():
    from httpx import AsyncClient
    from main import app
    import asyncio
    return AsyncClient(app=app, base_url="http://test")

@pytest.mark.asyncio
async def test_health_endpoint(client):
    async with client as c:
        resp = await c.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_event_stored(client):
    from database import get_events_last_n_days
    import time
    async with client as c:
        resp = await c.post("/event", json={
            "url": "https://github.com/anthropics/mcp",
            "title": "MCP Python SDK",
            "time_spent_seconds": 180,
            "timestamp": int(time.time() * 1000)
        })
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    events = get_events_last_n_days(1)
    assert len(events) == 1
    assert events[0]["domain"] == "github.com"

@pytest.mark.asyncio
async def test_localhost_events_skipped(client):
    from database import get_events_last_n_days
    import time
    async with client as c:
        resp = await c.post("/event", json={
            "url": "http://localhost:3000/dashboard",
            "title": "Local Dev",
            "time_spent_seconds": 10,
            "timestamp": int(time.time() * 1000)
        })
    assert resp.json()["status"] == "skipped"
    assert get_events_last_n_days(1) == []

@pytest.mark.asyncio
async def test_search_query_extracted(client):
    from database import get_events_last_n_days
    import time
    async with client as c:
        await c.post("/event", json={
            "url": "https://www.google.com/search?q=mcp+server+tutorial",
            "title": "mcp server tutorial - Google Search",
            "time_spent_seconds": 5,
            "timestamp": int(time.time() * 1000)
        })
    events = get_events_last_n_days(1)
    assert events[0]["search_query"] == "mcp server tutorial"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_main.py -v
```

Expected: `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 3: Implement main.py**

```python
# backend/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
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


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=7823)
```

- [ ] **Step 4: Create minimal scheduler.py (needed by main.py import)**

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_main.py -v
```

Expected output:
```
test_main.py::test_health_endpoint PASSED
test_main.py::test_event_stored PASSED
test_main.py::test_localhost_events_skipped PASSED
test_main.py::test_search_query_extracted PASSED
4 passed
```

- [ ] **Step 6: Smoke test server manually**

```bash
cd backend
cp .env.example .env
python main.py &
curl http://localhost:7823/health
```

Expected: `{"status":"ok","service":"personalayer"}`

Kill the background server: `kill %1`

- [ ] **Step 7: Commit**

```bash
git add backend/main.py backend/scheduler.py
git commit -m "feat: add FastAPI event receiver with domain extraction and skip logic"
```

---

## Task 4: Chrome Extension

**Files:**
- Create: `extension/manifest.json`
- Create: `extension/background.js`
- Create: `extension/content.js`
- Create: `extension/icons/icon128.png` (any 128x128 PNG — use placeholder)

*Note: Chrome extensions cannot be unit tested with pytest. Testing is manual load + verify.*

- [ ] **Step 1: Create manifest.json**

```json
{
  "manifest_version": 3,
  "name": "PersonaLayer",
  "version": "1.0.0",
  "description": "Builds your AI persona from browsing activity. All data stays local.",
  "permissions": ["tabs", "storage"],
  "host_permissions": ["http://localhost:7823/*"],
  "background": {
    "service_worker": "background.js"
  },
  "content_scripts": [
    {
      "matches": ["http://*/*", "https://*/*"],
      "js": ["content.js"],
      "exclude_matches": [
        "*://localhost/*",
        "*://127.0.0.1/*"
      ]
    }
  ],
  "icons": {
    "128": "icons/icon128.png"
  }
}
```

- [ ] **Step 2: Create background.js**

```javascript
// extension/background.js
const ENDPOINT = "http://localhost:7823/event";

// tabData[tabId] = { url, title, startTime }
const tabData = {};

// When user switches to a tab, record start time
chrome.tabs.onActivated.addListener(({ tabId, previousTabId }) => {
  if (previousTabId !== undefined) {
    flushTab(previousTabId);
  }
  chrome.tabs.get(tabId, (tab) => {
    if (chrome.runtime.lastError || !tab) return;
    tabData[tabId] = {
      url: tab.url || "",
      title: tab.title || "",
      startTime: Date.now(),
    };
  });
});

// When a page finishes loading in a tab, reset its timer
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status !== "complete") return;
  if (!tab.url || isSkipped(tab.url)) return;
  tabData[tabId] = {
    url: tab.url,
    title: tab.title || "",
    startTime: Date.now(),
  };
});

// When a tab closes, flush it
chrome.tabs.onRemoved.addListener((tabId) => {
  flushTab(tabId);
  delete tabData[tabId];
});

function isSkipped(url) {
  return (
    url.startsWith("chrome://") ||
    url.startsWith("chrome-extension://") ||
    url.startsWith("about:") ||
    url.startsWith("http://localhost") ||
    url.startsWith("http://127.0.0.1")
  );
}

function flushTab(tabId) {
  const data = tabData[tabId];
  if (!data || !data.url || isSkipped(data.url)) return;

  const timeSpent = Math.floor((Date.now() - data.startTime) / 1000);
  if (timeSpent < 3) return; // skip flash navigations

  fetch(ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      url: data.url,
      title: data.title,
      time_spent_seconds: timeSpent,
      timestamp: Date.now(),
    }),
  }).catch(() => {
    // Server not running — silently ignore, no console spam
  });
}
```

- [ ] **Step 3: Create content.js**

```javascript
// extension/content.js
// v1: stub. Background handles all tracking via chrome.tabs API.
// v2: will extract page headings + article text for richer context.
```

- [ ] **Step 4: Create placeholder icon**

Download any 128x128 PNG and save as `extension/icons/icon128.png`.
Or generate one quickly:

```bash
# Mac/Linux — requires Python Pillow or just use any PNG
python3 -c "
from PIL import Image, ImageDraw
img = Image.new('RGB', (128, 128), color=(99, 102, 241))
d = ImageDraw.Draw(img)
d.text((40, 50), 'PL', fill=(255,255,255))
img.save('extension/icons/icon128.png')
" 2>/dev/null || echo "Manually add any PNG as extension/icons/icon128.png"
```

- [ ] **Step 5: Load extension in Chrome and verify**

1. Open Chrome → `chrome://extensions/`
2. Enable **Developer mode** (top right toggle)
3. Click **Load unpacked** → select the `extension/` folder
4. PersonaLayer extension appears in toolbar
5. Start backend: `cd backend && python main.py`
6. Browse to `https://github.com` for 5+ seconds, then switch tabs
7. Check SQLite directly:

```bash
python3 -c "
import sys; sys.path.insert(0,'backend')
from database import get_events_last_n_days
events = get_events_last_n_days(1)
print(f'{len(events)} events captured')
if events: print(events[0])
"
```

Expected: `1 events captured` with `domain: github.com`

- [ ] **Step 6: Commit**

```bash
git add extension/
git commit -m "feat: add Chrome extension MV3 with tab tracking and time-on-page"
```

---

## Task 5: Persona Extraction Engine

**Files:**
- Create: `backend/persona.py`
- Create: `tests/test_persona.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_persona.py
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

TEST_DIR = Path(tempfile.mkdtemp())

@pytest.fixture(autouse=True)
def use_test_paths(monkeypatch):
    import persona as p
    monkeypatch.setattr(p, 'DATA_DIR', TEST_DIR)
    monkeypatch.setattr(p, 'PERSONA_FILE', TEST_DIR / 'persona.json')


def make_events(n=20):
    import time
    now = int(time.time() * 1000)
    return [
        {
            "id": i,
            "url": f"https://github.com/page{i}",
            "title": f"GitHub Page {i}",
            "domain": "github.com",
            "time_spent_seconds": 120,
            "search_query": "mcp python" if i % 3 == 0 else None,
            "timestamp": now - i * 60000,
        }
        for i in range(n)
    ]


def test_summarize_events_top_domains():
    from persona import summarize_events
    events = make_events(10)
    summary = summarize_events(events)
    assert "github.com" in summary
    assert "TOP DOMAINS" in summary


def test_summarize_events_includes_searches():
    from persona import summarize_events
    events = make_events(10)
    summary = summarize_events(events)
    assert "mcp python" in summary


def test_summarize_events_empty():
    from persona import summarize_events
    result = summarize_events([])
    assert "no data" in result.lower() or result == ""


def test_extract_persona_writes_file():
    from persona import extract_persona

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({
        "identity": {"role": "developer", "expertise": ["Python"], "current_project": "PersonaLayer"},
        "voice": {"style": "terse", "formality": "casual-professional", "emoji": False},
        "decisions": {"optimizes_for": "speed", "risk_tolerance": "high", "instant_yes": ["open source"], "instant_no": ["vendor lock-in"]},
        "context": {"building": "MCP server", "blocked_on": "", "learning_this_week": ["MCP"], "active_hours": "22:00-02:00"},
        "interests": {"obsessions": ["AI agents"], "depth": {"expert": ["Python"], "learning": ["MCP"], "shallow": []}},
        "values": {"trusts": ["YC companies"], "dislikes": ["hype"]},
        "meta": {"updated_at": "2026-04-26T00:00:00", "data_window_days": 7, "event_count": 20}
    }))]

    with patch('persona.get_events_last_n_days', return_value=make_events(20)), \
         patch('persona.Anthropic') as mock_anthropic:
        mock_anthropic.return_value.messages.create.return_value = mock_response
        result = extract_persona()

    assert result["identity"]["role"] == "developer"
    persona_file = TEST_DIR / 'persona.json'
    assert persona_file.exists()
    saved = json.loads(persona_file.read_text())
    assert saved["identity"]["role"] == "developer"


def test_extract_persona_returns_empty_when_no_events():
    from persona import extract_persona
    with patch('persona.get_events_last_n_days', return_value=[]):
        result = extract_persona()
    assert result == {}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_persona.py -v
```

Expected: `ModuleNotFoundError: No module named 'persona'`

- [ ] **Step 3: Implement persona.py**

```python
# backend/persona.py
import json
import logging
from collections import Counter
from pathlib import Path
from typing import Optional

from anthropic import Anthropic
from dotenv import load_dotenv

from database import get_events_last_n_days, save_persona

load_dotenv()
logger = logging.getLogger(__name__)

DATA_DIR = Path.home() / ".personalayer"
PERSONA_FILE = DATA_DIR / "persona.json"

PERSONA_SCHEMA = {
    "identity": {"role": "string", "expertise": [], "current_project": "string"},
    "voice": {"style": "string", "formality": "string", "emoji": False},
    "decisions": {
        "optimizes_for": "string",
        "risk_tolerance": "string",
        "instant_yes": [],
        "instant_no": [],
    },
    "context": {
        "building": "string",
        "blocked_on": "string",
        "learning_this_week": [],
        "active_hours": "string",
    },
    "interests": {
        "obsessions": [],
        "depth": {"expert": [], "learning": [], "shallow": []},
    },
    "values": {"trusts": [], "dislikes": []},
    "meta": {"updated_at": "ISO-8601", "data_window_days": 7, "event_count": 0},
}


def summarize_events(events: list[dict]) -> str:
    if not events:
        return ""

    domain_seconds: Counter = Counter()
    searches: list[str] = []
    titles: list[str] = []

    for e in events:
        if e.get("domain"):
            domain_seconds[e["domain"]] += e.get("time_spent_seconds", 0)
        if e.get("search_query"):
            searches.append(e["search_query"])
        if e.get("title"):
            titles.append(e["title"])

    lines = ["TOP DOMAINS (time spent in seconds):"]
    for domain, secs in domain_seconds.most_common(25):
        lines.append(f"  {domain}: {secs}s")

    if searches:
        unique_searches = list(dict.fromkeys(searches))[-60:]
        lines.append(f"\nSEARCH QUERIES: {', '.join(unique_searches)}")

    if titles:
        sample_titles = titles[-40:]
        lines.append(f"\nPAGE TITLES (sample): {'; '.join(sample_titles)}")

    return "\n".join(lines)


def _parse_json_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def extract_persona() -> dict:
    events = get_events_last_n_days(7)
    if not events:
        logger.info("No events found — skipping persona extraction")
        return {}

    summary = summarize_events(events)
    client = Anthropic()

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=2048,
        system=(
            "You are a behavioral analyst. Extract a structured personality profile "
            "from browsing activity. Be specific and factual. "
            "No speculation beyond what the data shows. "
            "Return ONLY valid JSON — no explanation, no markdown, no preamble."
        ),
        messages=[
            {
                "role": "user",
                "content": (
                    f"Here is 7 days of browsing activity for one person:\n\n{summary}\n\n"
                    f"Return a JSON object with this exact structure:\n"
                    f"{json.dumps(PERSONA_SCHEMA, indent=2)}\n\n"
                    f"Rules:\n"
                    f"- Fill every field based on evidence in the data\n"
                    f"- active_hours: infer from which hours had most activity\n"
                    f"- updated_at: use ISO-8601 timestamp for right now\n"
                    f"- event_count: {len(events)}\n"
                    f"- Return ONLY the JSON object"
                ),
            }
        ],
    )

    persona = _parse_json_response(response.content[0].text)

    DATA_DIR.mkdir(exist_ok=True)
    PERSONA_FILE.write_text(json.dumps(persona, indent=2))
    save_persona(persona)

    logger.info("Persona written to %s", PERSONA_FILE)
    return persona


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = extract_persona()
    if result:
        print(json.dumps(result, indent=2))
    else:
        print("No events yet — browse for a while first")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_persona.py -v
```

Expected output:
```
test_persona.py::test_summarize_events_top_domains PASSED
test_persona.py::test_summarize_events_includes_searches PASSED
test_persona.py::test_summarize_events_empty PASSED
test_persona.py::test_extract_persona_writes_file PASSED
test_persona.py::test_extract_persona_returns_empty_when_no_events PASSED
5 passed
```

- [ ] **Step 5: Run manually with real data (requires ANTHROPIC_API_KEY in .env)**

```bash
cd backend
python persona.py
```

Expected: JSON persona printed to stdout, `~/.personalayer/persona.json` created.

- [ ] **Step 6: Commit**

```bash
git add backend/persona.py tests/test_persona.py backend/scheduler.py
git commit -m "feat: add persona extraction engine using Claude Haiku"
```

---

## Task 6: MCP Server

**Files:**
- Create: `backend/mcp_server.py`
- Create: `tests/test_mcp.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_mcp.py
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

TEST_DIR = Path(tempfile.mkdtemp())
SAMPLE_PERSONA = {
    "identity": {"role": "developer", "expertise": ["Python", "MCP"], "current_project": "PersonaLayer"},
    "voice": {"style": "terse", "formality": "casual-professional", "emoji": False},
    "decisions": {"optimizes_for": "speed", "risk_tolerance": "high", "instant_yes": ["open source"], "instant_no": ["vendor lock-in"]},
    "context": {"building": "MCP server", "blocked_on": "persona schema", "learning_this_week": ["MCP protocol"], "active_hours": "22:00-02:00"},
    "interests": {"obsessions": ["AI agents", "YC"], "depth": {"expert": ["Python"], "learning": ["vector DBs", "MCP"], "shallow": ["mobile"]}},
    "values": {"trusts": ["YC", "OSS"], "dislikes": ["hype"]},
    "meta": {"updated_at": "2026-04-26T00:00:00", "data_window_days": 7, "event_count": 150}
}


@pytest.fixture
def persona_file(tmp_path):
    f = tmp_path / "persona.json"
    f.write_text(json.dumps(SAMPLE_PERSONA))
    return f


def test_get_persona_returns_full_profile(persona_file):
    from mcp_server import handle_get_persona
    result = handle_get_persona(str(persona_file))
    data = json.loads(result)
    assert data["identity"]["role"] == "developer"
    assert data["identity"]["current_project"] == "PersonaLayer"


def test_get_persona_no_file():
    from mcp_server import handle_get_persona
    result = handle_get_persona("/nonexistent/persona.json")
    assert "no persona" in result.lower() or "not found" in result.lower()


def test_get_context_known_topic(persona_file):
    from mcp_server import handle_get_context
    result = handle_get_context("mcp", str(persona_file))
    data = json.loads(result)
    assert data["depth"] == "learning"


def test_get_context_expert_topic(persona_file):
    from mcp_server import handle_get_context
    result = handle_get_context("python", str(persona_file))
    data = json.loads(result)
    assert data["depth"] == "expert"


def test_get_context_unknown_topic(persona_file):
    from mcp_server import handle_get_context
    result = handle_get_context("blockchain", str(persona_file))
    data = json.loads(result)
    assert data["depth"] == "unknown"


def test_get_current_focus(persona_file):
    from mcp_server import handle_get_current_focus
    result = handle_get_current_focus(str(persona_file))
    data = json.loads(result)
    assert data["building"] == "MCP server"
    assert "MCP protocol" in data["learning_this_week"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_mcp.py -v
```

Expected: `ModuleNotFoundError: No module named 'mcp_server'`

- [ ] **Step 3: Implement mcp_server.py**

```python
# backend/mcp_server.py
import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_PERSONA_FILE = str(Path.home() / ".personalayer" / "persona.json")

server = Server("personalayer")


# ── Pure handler functions (testable without MCP machinery) ──────────────────

def handle_get_persona(persona_file: str = DEFAULT_PERSONA_FILE) -> str:
    path = Path(persona_file)
    if not path.exists():
        return json.dumps({"error": "No persona data yet. Browse for 24h or run: python persona.py"})
    return path.read_text()


def handle_get_context(topic: str, persona_file: str = DEFAULT_PERSONA_FILE) -> str:
    path = Path(persona_file)
    if not path.exists():
        return json.dumps({"error": "No persona data yet."})

    persona = json.loads(path.read_text())
    topic_lower = topic.lower()

    depth_map = persona.get("interests", {}).get("depth", {})
    matched_depth = "unknown"
    for level, topics in depth_map.items():
        if any(topic_lower in t.lower() for t in topics):
            matched_depth = level
            break

    obsessions = [
        o for o in persona.get("interests", {}).get("obsessions", [])
        if topic_lower in o.lower()
    ]

    return json.dumps({
        "topic": topic,
        "depth": matched_depth,
        "related_obsessions": obsessions,
        "current_project": persona.get("identity", {}).get("current_project", "unknown"),
    }, indent=2)


def handle_get_current_focus(persona_file: str = DEFAULT_PERSONA_FILE) -> str:
    path = Path(persona_file)
    if not path.exists():
        return json.dumps({"error": "No persona data yet."})

    persona = json.loads(path.read_text())
    return json.dumps(persona.get("context", {}), indent=2)


# ── MCP tool definitions ──────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_persona",
            description=(
                "Get the full persona profile of the user. "
                "Use this to understand who they are, their expertise, communication style, "
                "values, and decision-making patterns."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="get_context",
            description=(
                "Get the user's knowledge depth and interest level for a specific topic. "
                "Returns: depth (expert/learning/shallow/unknown) and related obsessions."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic to check, e.g. 'vector databases', 'Python', 'React'",
                    }
                },
                "required": ["topic"],
            },
        ),
        types.Tool(
            name="get_current_focus",
            description=(
                "Get what the user is currently working on, what's blocking them, "
                "what they're learning this week, and their active working hours."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "get_persona":
        text = handle_get_persona()
    elif name == "get_context":
        topic = arguments.get("topic", "")
        text = handle_get_context(topic)
    elif name == "get_current_focus":
        text = handle_get_current_focus()
    else:
        text = json.dumps({"error": f"Unknown tool: {name}"})

    return [types.TextContent(type="text", text=text)]


# ── Entry point ───────────────────────────────────────────────────────────────

async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_mcp.py -v
```

Expected output:
```
test_mcp.py::test_get_persona_returns_full_profile PASSED
test_mcp.py::test_get_persona_no_file PASSED
test_mcp.py::test_get_context_known_topic PASSED
test_mcp.py::test_get_context_expert_topic PASSED
test_mcp.py::test_get_context_unknown_topic PASSED
test_mcp.py::test_get_current_focus PASSED
6 passed
```

- [ ] **Step 5: Wire MCP server into Claude Desktop**

Create `claude_desktop_config.json.template`:

```json
{
  "mcpServers": {
    "personalayer": {
      "command": "python",
      "args": ["REPLACE_WITH_ABSOLUTE_PATH/backend/mcp_server.py"]
    }
  }
}
```

**Mac:** Merge into `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows:** Merge into `%APPDATA%\Claude\claude_desktop_config.json`

Replace `REPLACE_WITH_ABSOLUTE_PATH` with actual path, e.g. `/Users/yourname/personalayer`.

Restart Claude Desktop → open Claude → type: `What am I currently building?`

Expected: Claude returns content from your persona's `context.building` field.

- [ ] **Step 6: Commit**

```bash
git add backend/mcp_server.py tests/test_mcp.py claude_desktop_config.json.template
git commit -m "feat: add MCP server with get_persona, get_context, get_current_focus tools"
```

---

## Task 7: Dashboard

**Files:**
- Create: `dashboard/index.html`
- Create: `dashboard/style.css`

*Dashboard is served by FastAPI at `http://localhost:7823/dashboard`. No JS framework.*

- [ ] **Step 1: Create index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PersonaLayer</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header>
    <h1>PersonaLayer</h1>
    <p class="subtitle">What every AI now knows about you</p>
    <button id="refresh-btn" onclick="loadPersona()">Refresh</button>
    <button id="extract-btn" onclick="runExtraction()">Run Extraction Now</button>
  </header>

  <main id="main">
    <div id="loading">Loading persona...</div>
    <div id="error" style="display:none">
      <p>No persona yet.</p>
      <p>Browse the web for a while, then click <strong>Run Extraction Now</strong>.</p>
    </div>
    <div id="persona" style="display:none">
      <section class="card" id="identity-card"></section>
      <section class="card" id="context-card"></section>
      <section class="card" id="interests-card"></section>
      <section class="card" id="voice-card"></section>
      <section class="card" id="values-card"></section>
      <section class="card" id="meta-card"></section>
    </div>
  </main>

  <script>
    async function loadPersona() {
      document.getElementById('loading').style.display = 'block';
      document.getElementById('persona').style.display = 'none';
      document.getElementById('error').style.display = 'none';

      try {
        const resp = await fetch('/persona');
        const data = await resp.json();
        if (data.error) { showError(); return; }
        renderPersona(data);
      } catch (e) {
        showError();
      }
    }

    function showError() {
      document.getElementById('loading').style.display = 'none';
      document.getElementById('error').style.display = 'block';
    }

    function renderPersona(p) {
      document.getElementById('loading').style.display = 'none';
      document.getElementById('persona').style.display = 'grid';

      const id = p.identity || {};
      document.getElementById('identity-card').innerHTML = `
        <h2>Identity</h2>
        <p><strong>Role:</strong> ${id.role || '—'}</p>
        <p><strong>Current project:</strong> ${id.current_project || '—'}</p>
        <p><strong>Expertise:</strong> ${(id.expertise || []).join(', ') || '—'}</p>
      `;

      const ctx = p.context || {};
      document.getElementById('context-card').innerHTML = `
        <h2>Current Focus</h2>
        <p><strong>Building:</strong> ${ctx.building || '—'}</p>
        <p><strong>Blocked on:</strong> ${ctx.blocked_on || '—'}</p>
        <p><strong>Learning:</strong> ${(ctx.learning_this_week || []).join(', ') || '—'}</p>
        <p><strong>Active hours:</strong> ${ctx.active_hours || '—'}</p>
      `;

      const int = p.interests || {};
      const depth = int.depth || {};
      document.getElementById('interests-card').innerHTML = `
        <h2>Interests</h2>
        <p><strong>Obsessions:</strong> ${(int.obsessions || []).join(', ') || '—'}</p>
        <p><strong>Expert in:</strong> ${(depth.expert || []).join(', ') || '—'}</p>
        <p><strong>Learning:</strong> ${(depth.learning || []).join(', ') || '—'}</p>
      `;

      const v = p.voice || {};
      document.getElementById('voice-card').innerHTML = `
        <h2>Communication Style</h2>
        <p><strong>Style:</strong> ${v.style || '—'}</p>
        <p><strong>Formality:</strong> ${v.formality || '—'}</p>
        <p><strong>Emoji:</strong> ${v.emoji ? 'Yes' : 'No'}</p>
      `;

      const val = p.values || {};
      document.getElementById('values-card').innerHTML = `
        <h2>Values</h2>
        <p><strong>Trusts:</strong> ${(val.trusts || []).join(', ') || '—'}</p>
        <p><strong>Dislikes:</strong> ${(val.dislikes || []).join(', ') || '—'}</p>
      `;

      const meta = p.meta || {};
      document.getElementById('meta-card').innerHTML = `
        <h2>Meta</h2>
        <p><strong>Last updated:</strong> ${meta.updated_at || '—'}</p>
        <p><strong>Events analyzed:</strong> ${meta.event_count || '—'}</p>
        <p><strong>Data window:</strong> ${meta.data_window_days || 7} days</p>
      `;
    }

    async function runExtraction() {
      const btn = document.getElementById('extract-btn');
      btn.textContent = 'Running...';
      btn.disabled = true;
      try {
        const resp = await fetch('/extract', { method: 'POST' });
        const data = await resp.json();
        if (data.status === 'ok') {
          await loadPersona();
        } else {
          alert('Extraction failed: ' + (data.error || 'unknown error'));
        }
      } catch (e) {
        alert('Server not running or extraction failed.');
      } finally {
        btn.textContent = 'Run Extraction Now';
        btn.disabled = false;
      }
    }

    loadPersona();
  </script>
</body>
</html>
```

- [ ] **Step 2: Create style.css**

```css
/* dashboard/style.css */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: #0f0f11;
  color: #e2e8f0;
  min-height: 100vh;
  padding: 2rem;
}

header {
  margin-bottom: 2rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

h1 { font-size: 1.75rem; font-weight: 700; color: #a78bfa; }
.subtitle { color: #94a3b8; font-size: 0.95rem; flex: 1; }

button {
  background: #1e1b4b;
  color: #a78bfa;
  border: 1px solid #312e81;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.875rem;
  transition: background 0.15s;
}
button:hover { background: #312e81; }
button:disabled { opacity: 0.5; cursor: not-allowed; }

#loading, #error { color: #94a3b8; padding: 2rem 0; }
#error strong { color: #a78bfa; }

#persona {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1.25rem;
}

.card {
  background: #18181b;
  border: 1px solid #27272a;
  border-radius: 10px;
  padding: 1.25rem;
}

.card h2 {
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #a78bfa;
  margin-bottom: 0.85rem;
}

.card p { font-size: 0.9rem; color: #cbd5e1; margin-bottom: 0.5rem; line-height: 1.5; }
.card strong { color: #e2e8f0; }
```

- [ ] **Step 3: Add /extract endpoint to main.py**

Open `backend/main.py` and add after the `@app.get("/persona")` route:

```python
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
```

- [ ] **Step 4: Verify dashboard**

```bash
cd backend && python main.py &
open http://localhost:7823/dashboard   # Mac
# Windows: start http://localhost:7823/dashboard
```

Expected: Dashboard loads, shows persona cards (or "no persona" message if extraction hasn't run yet).

Click **Run Extraction Now** → cards populate.

- [ ] **Step 5: Commit**

```bash
git add dashboard/ backend/main.py
git commit -m "feat: add persona dashboard served at localhost:7823/dashboard"
```

---

## Task 8: Install Scripts

**Files:**
- Create: `install.sh`
- Create: `install.bat`

- [ ] **Step 1: Create install.sh (Mac/Linux)**

```bash
#!/usr/bin/env bash
# install.sh
set -euo pipefail

echo ""
echo "PersonaLayer — Setup"
echo "===================="

# Check Python 3.10+
PYTHON=$(command -v python3 || command -v python || echo "")
if [ -z "$PYTHON" ]; then
  echo "ERROR: Python 3.10+ required. Install from https://python.org"
  exit 1
fi

PY_VERSION=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python: $PY_VERSION"

# Create data dir
mkdir -p ~/.personalayer

# Install deps
echo ""
echo "Installing Python dependencies..."
cd "$(dirname "$0")/backend"
$PYTHON -m pip install -r requirements.txt --quiet

# Scaffold .env
if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "⚠️  ACTION NEEDED: Add your Anthropic API key to backend/.env"
  echo "   Get one at: https://console.anthropic.com"
fi

# Generate MCP config with absolute path
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MCP_CONFIG="$SCRIPT_DIR/claude_desktop_config_generated.json"

cat > "$MCP_CONFIG" << EOF
{
  "mcpServers": {
    "personalayer": {
      "command": "python3",
      "args": ["$SCRIPT_DIR/backend/mcp_server.py"]
    }
  }
}
EOF

echo ""
echo "✅ Installation complete!"
echo ""
echo "Next steps:"
echo ""
echo "1. Add API key:  nano backend/.env"
echo "2. Load extension:"
echo "   Chrome → chrome://extensions/ → Developer mode ON → Load unpacked → select 'extension/'"
echo "3. Start server:"
echo "   python3 backend/main.py"
echo "4. Add MCP to Claude Desktop:"
echo "   Merge $MCP_CONFIG into:"
echo "   ~/Library/Application Support/Claude/claude_desktop_config.json"
echo "5. Restart Claude Desktop"
echo "6. View dashboard: http://localhost:7823/dashboard"
```

- [ ] **Step 2: Create install.bat (Windows)**

```batch
@echo off
setlocal enabledelayedexpansion
echo.
echo PersonaLayer — Setup
echo ====================

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python 3.10+ required. Install from https://python.org
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo Python: %PY_VER%

if not exist "%USERPROFILE%\.personalayer" mkdir "%USERPROFILE%\.personalayer"

echo.
echo Installing Python dependencies...
cd /d "%~dp0backend"
python -m pip install -r requirements.txt --quiet

if not exist ".env" (
    copy .env.example .env >nul
    echo.
    echo WARNING: Add your Anthropic API key to backend\.env
    echo Get one at: https://console.anthropic.com
)

set SCRIPT_DIR=%~dp0
set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%
set MCP_CONFIG=%SCRIPT_DIR%\claude_desktop_config_generated.json

(
echo {
echo   "mcpServers": {
echo     "personalayer": {
echo       "command": "python",
echo       "args": ["%SCRIPT_DIR:\=/%/backend/mcp_server.py"]
echo     }
echo   }
echo }
) > "%MCP_CONFIG%"

echo.
echo Installation complete!
echo.
echo Next steps:
echo 1. Add API key: notepad backend\.env
echo 2. Load extension: Chrome - chrome://extensions/ - Developer mode ON - Load unpacked - select 'extension\'
echo 3. Start server: python backend\main.py
echo 4. Merge %MCP_CONFIG% into %%APPDATA%%\Claude\claude_desktop_config.json
echo 5. Restart Claude Desktop
echo 6. View dashboard: http://localhost:7823/dashboard
```

- [ ] **Step 3: Make install.sh executable**

```bash
chmod +x install.sh
```

- [ ] **Step 4: Test install script (dry run)**

```bash
# Mac
bash install.sh

# Windows
install.bat
```

Expected: Dependencies install, `.env` created, `claude_desktop_config_generated.json` created with absolute path.

- [ ] **Step 5: Commit**

```bash
git add install.sh install.bat
git commit -m "feat: add one-click install scripts for Mac and Windows"
```

---

## Task 9: Full Integration Test + Polish

**Files:**
- Modify: `backend/main.py` (add CORS headers for extension)
- Create: `tests/test_integration.py`

- [ ] **Step 1: Add CORS to main.py (extension needs it)**

Open `backend/main.py`. After `from fastapi import FastAPI` imports add:

```python
from fastapi.middleware.cors import CORSMiddleware
```

After `app = FastAPI(...)` line add:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["chrome-extension://*", "http://localhost:*"],
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)
```

- [ ] **Step 2: Write integration test**

```python
# tests/test_integration.py
"""
Integration test — runs the full pipeline:
event → SQLite → persona extraction (mocked) → MCP tools

Run with: pytest tests/test_integration.py -v
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import json
import time
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

TEST_DIR = Path(tempfile.mkdtemp())

MOCK_PERSONA = {
    "identity": {"role": "developer", "expertise": ["Python"], "current_project": "PersonaLayer"},
    "voice": {"style": "terse", "formality": "casual-professional", "emoji": False},
    "decisions": {"optimizes_for": "speed", "risk_tolerance": "high", "instant_yes": ["OSS"], "instant_no": []},
    "context": {"building": "MCP server", "blocked_on": "", "learning_this_week": ["MCP"], "active_hours": "22:00-02:00"},
    "interests": {"obsessions": ["AI agents"], "depth": {"expert": ["Python"], "learning": ["MCP"], "shallow": []}},
    "values": {"trusts": ["YC"], "dislikes": ["hype"]},
    "meta": {"updated_at": "2026-04-26T00:00:00", "data_window_days": 7, "event_count": 50}
}


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    import database, persona
    monkeypatch.setattr(database, 'DATA_DIR', TEST_DIR)
    monkeypatch.setattr(database, 'DB_PATH', TEST_DIR / 'integration.db')
    monkeypatch.setattr(persona, 'DATA_DIR', TEST_DIR)
    monkeypatch.setattr(persona, 'PERSONA_FILE', TEST_DIR / 'persona.json')
    import database as db
    db.create_tables()


@pytest.mark.asyncio
async def test_full_pipeline():
    """Event ingested → persona extracted → MCP tools return data."""
    from httpx import AsyncClient
    from main import app
    from mcp_server import handle_get_persona, handle_get_context, handle_get_current_focus

    # 1. Ingest 5 browsing events
    async with AsyncClient(app=app, base_url="http://test") as client:
        for i in range(5):
            resp = await client.post("/event", json={
                "url": f"https://github.com/anthropics/repo{i}",
                "title": f"GitHub Repo {i}",
                "time_spent_seconds": 120,
                "timestamp": int(time.time() * 1000) - i * 60000,
            })
            assert resp.json()["status"] == "ok"

    # 2. Mock Claude and run extraction
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=json.dumps(MOCK_PERSONA))]

    persona_file = str(TEST_DIR / 'persona.json')
    with patch('persona.Anthropic') as mock_client:
        mock_client.return_value.messages.create.return_value = mock_resp
        from persona import extract_persona
        result = extract_persona()

    assert result["identity"]["role"] == "developer"

    # 3. MCP tools read the persona correctly
    persona_data = json.loads(handle_get_persona(persona_file))
    assert persona_data["identity"]["current_project"] == "PersonaLayer"

    ctx = json.loads(handle_get_context("python", persona_file))
    assert ctx["depth"] == "expert"

    focus = json.loads(handle_get_current_focus(persona_file))
    assert focus["building"] == "MCP server"
```

- [ ] **Step 3: Run full test suite**

```bash
pytest tests/ -v
```

Expected output:
```
tests/test_database.py::test_create_tables_is_idempotent PASSED
tests/test_database.py::test_insert_and_retrieve_event PASSED
tests/test_database.py::test_search_query_stored PASSED
tests/test_database.py::test_old_events_excluded PASSED
tests/test_database.py::test_save_and_get_persona PASSED
tests/test_main.py::test_health_endpoint PASSED
tests/test_main.py::test_event_stored PASSED
tests/test_main.py::test_localhost_events_skipped PASSED
tests/test_main.py::test_search_query_extracted PASSED
tests/test_persona.py::test_summarize_events_top_domains PASSED
tests/test_persona.py::test_summarize_events_includes_searches PASSED
tests/test_persona.py::test_summarize_events_empty PASSED
tests/test_persona.py::test_extract_persona_writes_file PASSED
tests/test_persona.py::test_extract_persona_returns_empty_when_no_events PASSED
tests/test_mcp.py::test_get_persona_returns_full_profile PASSED
tests/test_mcp.py::test_get_persona_no_file PASSED
tests/test_mcp.py::test_get_context_known_topic PASSED
tests/test_mcp.py::test_get_context_expert_topic PASSED
tests/test_mcp.py::test_get_context_unknown_topic PASSED
tests/test_mcp.py::test_get_current_focus PASSED
tests/test_integration.py::test_full_pipeline PASSED
21 passed
```

- [ ] **Step 4: End-to-end manual demo**

```bash
# Terminal 1: start server
cd backend && python main.py

# Terminal 2: simulate browsing events
python3 - << 'EOF'
import requests, time
events = [
    {"url": "https://github.com/anthropics/anthropic-sdk-python", "title": "Anthropic Python SDK", "time_spent_seconds": 300, "timestamp": int(time.time()*1000)},
    {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "title": "AI Agent Tutorial", "time_spent_seconds": 600, "timestamp": int(time.time()*1000)-5000},
    {"url": "https://google.com/search?q=mcp+server+python+tutorial", "title": "mcp server - Google", "time_spent_seconds": 30, "timestamp": int(time.time()*1000)-10000},
]
for e in events:
    r = requests.post("http://localhost:7823/event", json=e)
    print(r.json())
EOF

# Terminal 2: run extraction
cd backend && python persona.py

# Open Claude Desktop → type:
# "What am I currently building?"
# Expected: Mentions PersonaLayer / MCP server
```

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete PersonaLayer MVP — extension, FastAPI, persona engine, MCP server, dashboard"
```

---

## Day-by-Day Reference

| Day | Tasks | End state |
|-----|-------|-----------|
| **1** | Task 1 + 2 + 3 | Extension sending events, FastAPI storing to SQLite |
| **2** | Task 4 + 5 (scheduler) | Persona extracts from real data, nightly job running |
| **3** | Task 6 | MCP server in Claude Desktop, tools working |
| **4** | Task 7 + 8 | Dashboard live, install scripts tested |
| **5** | Task 9 | All 21 tests pass, demo video recorded |

---

## Success Criteria Checklist

- [ ] Chrome extension captures browsing events silently
- [ ] Events appear in `~/.personalayer/data.db` within seconds
- [ ] `python backend/persona.py` produces filled persona JSON
- [ ] Claude Desktop lists `get_persona`, `get_context`, `get_current_focus` tools
- [ ] `get_persona()` returns accurate profile
- [ ] Dashboard at `localhost:7823/dashboard` shows persona cards
- [ ] `install.sh` / `install.bat` works on fresh machine
- [ ] All 21 tests pass: `pytest tests/ -v`
- [ ] Demo: open Claude, ask "what am I building?" → correct answer
