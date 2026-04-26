# PersonaLayer MVP — Design Spec
**Date:** 2026-04-26  
**Status:** Approved  
**Build target:** 5 days  
**Stack:** Python (backend) + Chrome Extension (MV3) + SQLite  
**Platform:** Mac + Windows

---

## What We're Building

PersonaLayer is the identity layer for AI agents. It captures your digital behavior, extracts a structured personality model, and exposes it as an MCP server — so every AI tool you use already knows who you are, what you're building, and how you think.

**Core wow moment:**
> User opens Claude Desktop. Without typing anything, Claude already knows what the user is building, their interests, their communication style, and their current focus.

---

## Problem

Every AI treats every user like a stranger. Context window starts empty. User repeats themselves endlessly. Personalization = manually written system prompts nobody maintains.

**PersonaLayer fixes this permanently.**

---

## Architecture

```
Chrome Extension (MV3)
  Captures: URL, title, time spent, domain, search queries
  Trigger: every tab change + page unload
  Sends: HTTP POST → localhost:7823
          ↓
FastAPI Server (Python, localhost:7823)
  Receives browsing events
  Stores to SQLite (local file, never leaves device)
  Runs nightly persona extraction job
          ↓
SQLite Database (~/.personalayer/data.db)
  Table: events (raw browsing)
  Table: persona (extracted profile)
          ↓
Persona Engine (Python + Claude API)
  Reads 7-day event window
  Calls Claude API with anonymized activity summary
  Writes structured persona JSON
          ↓
MCP Server (Python MCP SDK)
  Exposes 3 tools to any MCP client
  Works with Claude Desktop + Cursor out of box
```

---

## File Structure

```
personalayer/
├── extension/
│   ├── manifest.json           # MV3 config
│   ├── background.js           # Tab tracking service worker
│   ├── content.js              # Time-on-page tracker
│   └── icons/
│
├── backend/
│   ├── main.py                 # FastAPI — receives events from extension
│   ├── database.py             # SQLite read/write operations
│   ├── persona.py              # Claude API persona extraction
│   ├── mcp_server.py           # MCP server — 3 tools
│   ├── scheduler.py            # Nightly persona refresh (APScheduler)
│   ├── requirements.txt
│   └── .env                    # ANTHROPIC_API_KEY
│
├── dashboard/
│   ├── index.html              # View + edit persona
│   └── style.css
│
├── install.sh                  # Mac one-click setup
├── install.bat                 # Windows one-click setup
└── claude_desktop_config.json  # Drop-in Claude Desktop MCP config
```

---

## Persona JSON Schema

```json
{
  "identity": {
    "role": "string — inferred job/focus",
    "expertise": ["array of skill areas"],
    "current_project": "string — what they're building now"
  },
  "voice": {
    "style": "string — terse/verbose/balanced (inferred from content consumed, not writing)",
    "formality": "casual | professional | casual-professional",
    "emoji": "boolean (inferred from social content engagement)",
    "note": "v1: inferred from consumption patterns only. Writing analysis = v2 (needs email/docs access)"
  },
  "decisions": {
    "optimizes_for": "string — speed/quality/cost/learning",
    "risk_tolerance": "low | medium | high",
    "instant_yes": ["inferred from: tools visited repeatedly, GitHub repos starred, search patterns"],
    "instant_no": ["inferred from: topics avoided, tools never revisited, negative search terms"]
  },
  "context": {
    "building": "string — current project",
    "blocked_on": "string — current obstacle",
    "learning_this_week": ["active learning topics"],
    "active_hours": "string — e.g. 22:00-02:00"
  },
  "interests": {
    "obsessions": ["topics returned to weekly"],
    "depth": {
      "expert": ["topics"],
      "learning": ["topics"],
      "shallow": ["topics"]
    }
  },
  "values": {
    "trusts": ["sources, people, frameworks trusted"],
    "dislikes": ["what they avoid or reject"]
  },
  "meta": {
    "updated_at": "ISO timestamp",
    "data_window_days": 7,
    "event_count": "number of events in window"
  }
}
```

---

## MCP Server — 3 Tools

### `get_persona()`
Returns full persona JSON.  
**Use case:** Inject into any agent system prompt as user context.

### `get_context(topic: str)`
Returns user's knowledge depth and recent activity on a specific topic.  
**Example:** `get_context("vector databases")` → `{ "depth": "learning", "recent_activity": "12 visits this week", "last_seen": "2026-04-25" }`

### `get_current_focus()`
Returns current project, blockers, and active learning.  
**Use case:** Agent picks up exactly where user left off without asking.

---

## Chrome Extension — Data Captured

| Field | Source | Example |
|---|---|---|
| url | Tab URL | https://github.com/... |
| title | Page title | "mcp-python-sdk/README.md" |
| domain | Extracted from URL | github.com |
| time_spent_seconds | Page unload event | 847 |
| timestamp | Date.now() | 1745678400000 |
| search_query | URL params (Google/YouTube/GitHub) | "mcp server python" |

**Not captured:** Page content, passwords, form inputs, incognito tabs.

---

## Persona Extraction — Claude API Prompt

```
System: You are a behavioral analyst. Extract a structured personality 
profile from browsing activity. Be specific and factual. 
No speculation beyond the data.

User: Here is 7 days of browsing activity for one person:
[anonymized domain + title + time_spent summary]

Return a JSON object matching this schema: [schema]
Focus on: what they're building, how they think, 
what they care about, their communication style.
```

Runs nightly at 2am local time via APScheduler.  
Cost: ~$0.05 per extraction run per user.

---

## Privacy Model

- All raw data stored locally: `~/.personalayer/data.db`
- Persona JSON stored locally: `~/.personalayer/persona.json`
- FastAPI server binds to `localhost:7823` only — no external exposure
- Extension does not capture: incognito tabs, passwords, form inputs, page content
- Only external network call: Claude API (receives anonymized domain+title summary, never raw URLs with sensitive params — search queries stripped of PII before sending)
- No user accounts, no telemetry, no analytics

---

## 5-Day Build Plan

| Day | Deliverable | Done when |
|-----|------------|-----------|
| **1** | Chrome extension + FastAPI receiver + SQLite schema | Browse Chrome → rows appear in SQLite |
| **2** | Persona extraction engine (Claude API → persona JSON) | Run script → get filled persona matching schema |
| **3** | MCP server with 3 tools working | Claude Desktop queries tools → returns persona data |
| **4** | Dashboard (view/edit persona) + install scripts | Browser shows persona, edit saves, install works one-click |
| **5** | Cross-platform testing + polish + demo video | Works on Mac + Windows, demo recorded |

---

## Tech Stack

| Layer | Tech | Version |
|---|---|---|
| Chrome Extension | Vanilla JS, Manifest V3 | Chrome 120+ |
| Backend server | FastAPI | 0.115+ |
| Database | SQLite via Python sqlite3 | stdlib |
| Persona extraction | Anthropic Python SDK | latest |
| MCP server | mcp Python SDK | latest |
| Scheduler | APScheduler | 3.x |
| Dashboard | Plain HTML/CSS/JS | — |

---

## Claude Desktop Integration

User drops this into `~/Library/Application Support/Claude/claude_desktop_config.json` (Mac) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "personalayer": {
      "command": "python",
      "args": ["/path/to/personalayer/backend/mcp_server.py"]
    }
  }
}
```

Restart Claude Desktop → tools available instantly.

---

## Success Criteria (MVP)

1. Chrome extension captures browsing silently, zero UX friction
2. Persona JSON generated within 24 hours of install
3. Claude Desktop can call all 3 MCP tools and return accurate persona data
4. Works on both Mac and Windows with one install command
5. Demo: open Claude, ask "what am I building?" — correct answer, zero setup by user

---

## Out of Scope (v1)

- Transaction authorization layer
- Social media ingestion (X, Instagram, YouTube)
- Mobile app
- Multi-device sync
- Custom LLM fine-tuning / LoRA adapters
- User accounts / cloud storage
- Team/enterprise features
- Paid tier / billing
