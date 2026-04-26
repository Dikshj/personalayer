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
