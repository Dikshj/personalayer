import sqlite3
from collections.abc import Callable


Migration = Callable[[sqlite3.Connection], None]


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _migration_001_context_contract_status(conn: sqlite3.Connection) -> None:
    ensure_column(conn, "context_contracts", "status", "TEXT DEFAULT 'active'")
    ensure_column(conn, "context_contracts", "revoked_at", "DATETIME")


def _migration_002_persona_feedback_calibration(conn: sqlite3.Connection) -> None:
    ensure_column(conn, "persona_feedback", "scope", "TEXT DEFAULT 'global'")
    ensure_column(conn, "persona_feedback", "target", "TEXT DEFAULT 'signal'")
    ensure_column(conn, "persona_feedback", "correction", "TEXT DEFAULT ''")
    ensure_column(conn, "persona_feedback", "importance", "REAL DEFAULT 1.0")
    ensure_column(conn, "persona_feedback", "confidence", "REAL DEFAULT 1.0")
    ensure_column(conn, "persona_feedback", "privacy", "TEXT DEFAULT 'normal'")
    ensure_column(conn, "persona_feedback", "temporal_scope", "TEXT DEFAULT 'persistent'")


def _migration_003_contextlayer_refresh_columns(conn: sqlite3.Connection) -> None:
    ensure_column(conn, "raw_events", "metadata", "TEXT DEFAULT '{}'")


MIGRATIONS: tuple[tuple[str, Migration], ...] = (
    ("001_context_contract_status", _migration_001_context_contract_status),
    ("002_persona_feedback_calibration", _migration_002_persona_feedback_calibration),
    ("003_contextlayer_refresh_columns", _migration_003_contextlayer_refresh_columns),
)


def run_migrations(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id TEXT PRIMARY KEY,
            applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    applied = {
        row["id"]
        for row in conn.execute("SELECT id FROM schema_migrations").fetchall()
    }
    for migration_id, migration in MIGRATIONS:
        if migration_id in applied:
            continue
        migration(conn)
        conn.execute(
            "INSERT INTO schema_migrations (id) VALUES (?)",
            (migration_id,),
        )
