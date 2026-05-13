import sqlite3
import json
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from storage.migrations import ensure_column, run_migrations

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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS waitlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                source TEXT DEFAULT 'landing',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feed_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                content_type TEXT NOT NULL,
                content TEXT NOT NULL,
                author TEXT DEFAULT '',
                url TEXT DEFAULT '',
                timestamp INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS persona_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                name TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                confidence REAL DEFAULT 0.5,
                evidence TEXT DEFAULT '',
                shareable INTEGER DEFAULT 1,
                timestamp INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS context_contracts (
                id TEXT PRIMARY KEY,
                platform_type TEXT NOT NULL,
                facilities TEXT NOT NULL,
                purpose TEXT DEFAULT '',
                retention TEXT DEFAULT 'session_only',
                granted_context TEXT NOT NULL,
                denied_context TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                revoked_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS context_access_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id TEXT NOT NULL,
                platform_type TEXT DEFAULT '',
                action TEXT NOT NULL,
                fields_returned TEXT DEFAULT '[]',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS persona_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_type TEXT NOT NULL,
                name TEXT NOT NULL,
                action TEXT NOT NULL,
                reason TEXT DEFAULT '',
                scope TEXT DEFAULT 'global',
                target TEXT DEFAULT 'signal',
                correction TEXT DEFAULT '',
                importance REAL DEFAULT 1.0,
                confidence REAL DEFAULT 1.0,
                privacy TEXT DEFAULT 'normal',
                temporal_scope TEXT DEFAULT 'persistent',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pcl_apps (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                allowed_layers TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                revoked_at DATETIME
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pcl_query_logs (
                id TEXT PRIMARY KEY,
                app_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                purpose TEXT DEFAULT '',
                requested_layers TEXT DEFAULT '[]',
                returned_layers TEXT DEFAULT '[]',
                feature_ids TEXT DEFAULT '[]',
                status TEXT NOT NULL,
                reason TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pcl_onboarding_seeds (
                user_id TEXT PRIMARY KEY,
                answers TEXT NOT NULL,
                profile_seed TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pcl_feature_events (
                id TEXT PRIMARY KEY,
                app_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                feature_id TEXT NOT NULL,
                feature_name TEXT DEFAULT '',
                event_type TEXT DEFAULT 'used',
                weight REAL DEFAULT 1.0,
                metadata TEXT DEFAULT '{}',
                timestamp INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pcl_integrations (
                source TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT DEFAULT 'connected',
                scopes TEXT DEFAULT '[]',
                metadata TEXT DEFAULT '{}',
                last_sync_at DATETIME,
                last_sync_status TEXT DEFAULT '',
                items_synced INTEGER DEFAULT 0,
                error TEXT DEFAULT '',
                connected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                disconnected_at DATETIME
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS raw_events (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                app_id TEXT NOT NULL,
                feature_id TEXT NOT NULL,
                action TEXT NOT NULL CHECK(action IN ('used','skipped','searched','dismissed')),
                session_id TEXT DEFAULT '',
                source TEXT NOT NULL CHECK(source IN ('sdk','extension','connector','onboarding')),
                is_synthetic INTEGER DEFAULT 0,
                metadata TEXT DEFAULT '{}',
                timestamp INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_raw_events_user_recent
            ON raw_events(user_id, created_at DESC)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feature_signals (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                app_id TEXT NOT NULL,
                feature_id TEXT NOT NULL,
                namespace TEXT NOT NULL,
                usage_count INTEGER DEFAULT 0,
                skipped_count INTEGER DEFAULT 0,
                dismissed_count INTEGER DEFAULT 0,
                last_used_at INTEGER,
                recency_score REAL DEFAULT 0,
                decay_score REAL DEFAULT 1.0,
                tier TEXT DEFAULT 'episodic' CHECK(tier IN ('core','episodic')),
                abstract_attributes TEXT DEFAULT '[]',
                is_synthetic INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, app_id, feature_id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_feature_signals_user_app
            ON feature_signals(user_id, app_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_feature_signals_recency
            ON feature_signals(user_id, recency_score DESC)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS privacy_filter_drops (
                id TEXT PRIMARY KEY,
                user_id TEXT DEFAULT '',
                app_id TEXT DEFAULT '',
                feature_id TEXT DEFAULT '',
                reason TEXT NOT NULL,
                source TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS context_bundles (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                app_id TEXT NOT NULL,
                feature_ids TEXT DEFAULT '[]',
                expires_at INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback_events (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                bundle_id TEXT NOT NULL,
                app_id TEXT NOT NULL,
                outcome TEXT NOT NULL CHECK(outcome IN ('accepted','rejected','modified')),
                features_actually_used TEXT DEFAULT '[]',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS active_context (
                user_id TEXT PRIMARY KEY,
                project TEXT DEFAULT '',
                active_apps TEXT DEFAULT '[]',
                session_start INTEGER NOT NULL,
                last_heartbeat INTEGER NOT NULL,
                inferred_intent TEXT DEFAULT '',
                session_depth TEXT DEFAULT 'shallow',
                expires_at INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS developers (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                name TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS apps (
                id TEXT PRIMARY KEY,
                developer_id TEXT DEFAULT '',
                app_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                domain TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id TEXT PRIMARY KEY,
                developer_id TEXT NOT NULL,
                app_id TEXT DEFAULT '',
                key_hash TEXT UNIQUE NOT NULL,
                key_prefix TEXT NOT NULL,
                env TEXT DEFAULT 'test',
                is_active INTEGER DEFAULT 1,
                last_used_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_permissions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                app_id TEXT NOT NULL,
                developer_id TEXT DEFAULT '',
                scopes TEXT DEFAULT '["getFeatureUsage"]',
                granted_via TEXT DEFAULT 'explicit',
                is_active INTEGER DEFAULT 1,
                granted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                revoked_at DATETIME,
                UNIQUE(user_id, app_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id TEXT PRIMARY KEY,
                abstract_attributes TEXT DEFAULT '[]',
                context_brief TEXT DEFAULT '',
                daily_insight TEXT DEFAULT '',
                last_synthesized_at INTEGER,
                last_refresh_at INTEGER,
                timezone TEXT DEFAULT 'UTC',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_refresh_jobs (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                timezone TEXT DEFAULT 'UTC',
                step_completed INTEGER DEFAULT 0,
                status TEXT DEFAULT 'running',
                error TEXT DEFAULT '',
                last_refresh_at INTEGER,
                started_at INTEGER NOT NULL,
                completed_at INTEGER,
                updated_at INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_refresh_step_logs (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                step_number INTEGER NOT NULL,
                step_name TEXT NOT NULL,
                status TEXT NOT NULL,
                error TEXT DEFAULT '',
                created_at INTEGER NOT NULL
            )
        """)
        run_migrations(conn)
        conn.commit()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    ensure_column(conn, table, column, definition)


def add_to_waitlist(email: str, source: str = "landing") -> bool:
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO waitlist (email, source) VALUES (?, ?)",
                (email.strip().lower(), source),
            )
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # already on waitlist


def get_waitlist_count() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) as c FROM waitlist").fetchone()
    return row["c"] if row else 0


def get_all_waitlist_emails() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT email, source, created_at FROM waitlist ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


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


def insert_feed_item(
    source: str,
    content_type: str,
    content: str,
    author: str,
    url: str,
    timestamp: int,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO feed_items
               (source, content_type, content, author, url, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (source, content_type, content[:2000], author, url, timestamp),
        )
        conn.commit()


def get_feed_items_last_n_days(n: int, source: Optional[str] = None) -> list[dict]:
    cutoff_ms = int((datetime.now() - timedelta(days=n)).timestamp() * 1000)
    with get_connection() as conn:
        if source:
            rows = conn.execute(
                "SELECT * FROM feed_items WHERE timestamp >= ? AND source = ? ORDER BY timestamp DESC",
                (cutoff_ms, source),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM feed_items WHERE timestamp >= ? ORDER BY timestamp DESC",
                (cutoff_ms,),
            ).fetchall()
    return [dict(row) for row in rows]


def insert_persona_signal(
    source: str,
    signal_type: str,
    name: str,
    weight: float,
    confidence: float,
    evidence: str,
    timestamp: int,
    shareable: bool = True,
) -> None:
    if not name.strip():
        return
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO persona_signals
               (source, signal_type, name, weight, confidence, evidence, shareable, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                source,
                signal_type,
                name.strip()[:160],
                float(weight),
                float(confidence),
                evidence[:500],
                1 if shareable else 0,
                timestamp,
            ),
        )
        conn.commit()


def get_persona_signals_last_n_days(n: int, shareable_only: bool = False) -> list[dict]:
    cutoff_ms = int((datetime.now() - timedelta(days=n)).timestamp() * 1000)
    with get_connection() as conn:
        if shareable_only:
            rows = conn.execute(
                """SELECT * FROM persona_signals
                   WHERE timestamp >= ? AND shareable = 1
                   ORDER BY timestamp DESC""",
                (cutoff_ms,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM persona_signals WHERE timestamp >= ? ORDER BY timestamp DESC",
                (cutoff_ms,),
            ).fetchall()
    return [dict(row) for row in rows]


def save_context_contract(contract: dict) -> None:
    with get_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO context_contracts
               (id, platform_type, facilities, purpose, retention, granted_context, denied_context)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                contract["contract_id"],
                contract["platform_type"],
                json.dumps(contract["facilities"]),
                contract.get("purpose", ""),
                contract.get("retention", "session_only"),
                json.dumps(contract["granted_context"]),
                json.dumps(contract["denied_context"]),
            ),
        )
        conn.commit()


def get_context_contract(contract_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM context_contracts WHERE id = ?",
            (contract_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "contract_id": row["id"],
        "platform_type": row["platform_type"],
        "facilities": json.loads(row["facilities"]),
        "purpose": row["purpose"],
        "retention": row["retention"],
        "granted_context": json.loads(row["granted_context"]),
        "denied_context": json.loads(row["denied_context"]),
        "status": row["status"],
        "revoked_at": row["revoked_at"],
        "created_at": row["created_at"],
    }


def list_context_contracts(limit: int = 50) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM context_contracts
               ORDER BY created_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [
        {
            "contract_id": row["id"],
            "platform_type": row["platform_type"],
            "facilities": json.loads(row["facilities"]),
            "purpose": row["purpose"],
            "retention": row["retention"],
            "granted_context": json.loads(row["granted_context"]),
            "denied_context": json.loads(row["denied_context"]),
            "status": row["status"],
            "revoked_at": row["revoked_at"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def revoke_context_contract(contract_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            """UPDATE context_contracts
               SET status = 'revoked', revoked_at = CURRENT_TIMESTAMP
               WHERE id = ? AND status != 'revoked'""",
            (contract_id,),
        )
        conn.commit()
    return cursor.rowcount > 0


def insert_context_access_log(
    contract_id: str,
    platform_type: str,
    action: str,
    fields_returned: list[str] | None = None,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO context_access_logs
               (contract_id, platform_type, action, fields_returned)
               VALUES (?, ?, ?, ?)""",
            (contract_id, platform_type, action, json.dumps(fields_returned or [])),
        )
        conn.commit()


def get_context_access_logs(contract_id: Optional[str] = None, limit: int = 100) -> list[dict]:
    with get_connection() as conn:
        if contract_id:
            rows = conn.execute(
                """SELECT * FROM context_access_logs
                   WHERE contract_id = ?
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (contract_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM context_access_logs
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
    return [
        {
            "id": row["id"],
            "contract_id": row["contract_id"],
            "platform_type": row["platform_type"],
            "action": row["action"],
            "fields_returned": json.loads(row["fields_returned"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def insert_persona_feedback(
    signal_type: str,
    name: str,
    action: str,
    reason: str = "",
    scope: str = "global",
    target: str = "signal",
    correction: str = "",
    importance: float = 1.0,
    confidence: float = 1.0,
    privacy: str = "normal",
    temporal_scope: str = "persistent",
) -> dict:
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO persona_feedback
               (signal_type, name, action, reason, scope, target, correction,
                importance, confidence, privacy, temporal_scope)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                signal_type,
                name.strip()[:160],
                action,
                reason[:500],
                scope[:80],
                target[:80],
                correction[:500],
                max(0.0, min(float(importance), 3.0)),
                max(0.0, min(float(confidence), 1.0)),
                privacy[:80],
                temporal_scope[:80],
            ),
        )
        conn.commit()
        feedback_id = cursor.lastrowid
    return {
        "id": feedback_id,
        "signal_type": signal_type,
        "name": name.strip()[:160],
        "action": action,
        "reason": reason[:500],
        "scope": scope[:80],
        "target": target[:80],
        "correction": correction[:500],
        "importance": max(0.0, min(float(importance), 3.0)),
        "confidence": max(0.0, min(float(confidence), 1.0)),
        "privacy": privacy[:80],
        "temporal_scope": temporal_scope[:80],
    }


def get_persona_feedback() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, signal_type, name, action, reason, scope, target,
                      correction, importance, confidence, privacy,
                      temporal_scope, created_at
               FROM persona_feedback
               ORDER BY created_at DESC"""
        ).fetchall()
    return [dict(row) for row in rows]


def get_persona_feedback_summary() -> dict:
    feedback = get_persona_feedback()
    by_action: dict[str, int] = {}
    by_privacy: dict[str, int] = {}
    calibration = []
    for item in feedback:
        by_action[item["action"]] = by_action.get(item["action"], 0) + 1
        by_privacy[item["privacy"]] = by_privacy.get(item["privacy"], 0) + 1
        if item.get("correction") or item.get("reason"):
            calibration.append({
                "signal_type": item["signal_type"],
                "name": item["name"],
                "action": item["action"],
                "correction": item.get("correction", ""),
                "reason": item.get("reason", ""),
                "scope": item.get("scope", "global"),
                "importance": item.get("importance", 1.0),
                "confidence": item.get("confidence", 1.0),
                "privacy": item.get("privacy", "normal"),
                "temporal_scope": item.get("temporal_scope", "persistent"),
                "created_at": item["created_at"],
            })
    return {
        "total": len(feedback),
        "by_action": by_action,
        "by_privacy": by_privacy,
        "calibration": calibration[:50],
    }


def get_activity_summary(days: int = 30) -> dict:
    cutoff_ms = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
    with get_connection() as conn:
        events = conn.execute(
            "SELECT COUNT(*) as c FROM events WHERE timestamp >= ?",
            (cutoff_ms,),
        ).fetchone()["c"]
        feed_items = conn.execute(
            "SELECT COUNT(*) as c FROM feed_items WHERE timestamp >= ?",
            (cutoff_ms,),
        ).fetchone()["c"]
        persona_signals = conn.execute(
            "SELECT COUNT(*) as c FROM persona_signals WHERE timestamp >= ?",
            (cutoff_ms,),
        ).fetchone()["c"]
        shareable_signals = conn.execute(
            """SELECT COUNT(*) as c FROM persona_signals
               WHERE timestamp >= ? AND shareable = 1""",
            (cutoff_ms,),
        ).fetchone()["c"]
        active_contracts = conn.execute(
            "SELECT COUNT(*) as c FROM context_contracts WHERE status = 'active'"
        ).fetchone()["c"]
        revoked_contracts = conn.execute(
            "SELECT COUNT(*) as c FROM context_contracts WHERE status = 'revoked'"
        ).fetchone()["c"]
        access_logs = conn.execute(
            "SELECT COUNT(*) as c FROM context_access_logs"
        ).fetchone()["c"]
        pcl_query_logs = conn.execute(
            "SELECT COUNT(*) as c FROM pcl_query_logs"
        ).fetchone()["c"]

    return {
        "days": days,
        "events": events,
        "feed_items": feed_items,
        "persona_signals": persona_signals,
        "shareable_signals": shareable_signals,
        "active_contracts": active_contracts,
        "revoked_contracts": revoked_contracts,
        "access_logs": access_logs,
        "pcl_query_logs": pcl_query_logs,
    }


def register_pcl_app(app_id: str, name: str, allowed_layers: list[str]) -> dict:
    app_id = app_id.strip()
    if not app_id:
        raise ValueError("app_id is required")
    with get_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO pcl_apps
               (id, name, allowed_layers, status, revoked_at)
               VALUES (?, ?, ?, 'active', NULL)""",
            (app_id, name.strip() or app_id, json.dumps(allowed_layers)),
        )
        conn.commit()
    return get_pcl_app(app_id) or {}


def get_pcl_app(app_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM pcl_apps WHERE id = ?",
            (app_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "app_id": row["id"],
        "name": row["name"],
        "allowed_layers": json.loads(row["allowed_layers"]),
        "status": row["status"],
        "created_at": row["created_at"],
        "revoked_at": row["revoked_at"],
    }


def list_pcl_apps(limit: int = 100) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM pcl_apps ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {
            "app_id": row["id"],
            "name": row["name"],
            "allowed_layers": json.loads(row["allowed_layers"]),
            "status": row["status"],
            "created_at": row["created_at"],
            "revoked_at": row["revoked_at"],
        }
        for row in rows
    ]


def revoke_pcl_app(app_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            """UPDATE pcl_apps
               SET status = 'revoked', revoked_at = CURRENT_TIMESTAMP
               WHERE id = ? AND status != 'revoked'""",
            (app_id,),
        )
        conn.commit()
    return cursor.rowcount > 0


def delete_pcl_app_data(app_id: str) -> dict:
    with get_connection() as conn:
        query_logs = conn.execute(
            "DELETE FROM pcl_query_logs WHERE app_id = ?",
            (app_id,),
        ).rowcount
        feature_events = conn.execute(
            "DELETE FROM pcl_feature_events WHERE app_id = ?",
            (app_id,),
        ).rowcount
        apps = conn.execute(
            "DELETE FROM pcl_apps WHERE id = ?",
            (app_id,),
        ).rowcount
        conn.commit()
    return {
        "app_id": app_id,
        "apps": apps,
        "query_logs": query_logs,
        "feature_events": feature_events,
    }


def insert_pcl_query_log(
    app_id: str,
    user_id: str,
    purpose: str,
    requested_layers: list[str],
    returned_layers: list[str],
    feature_ids: list[str],
    status: str,
    reason: str = "",
) -> dict:
    log_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO pcl_query_logs
               (id, app_id, user_id, purpose, requested_layers, returned_layers,
                feature_ids, status, reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                log_id,
                app_id,
                user_id,
                purpose,
                json.dumps(requested_layers),
                json.dumps(returned_layers),
                json.dumps(feature_ids),
                status,
                reason,
            ),
        )
        conn.commit()
    return {
        "id": log_id,
        "app_id": app_id,
        "user_id": user_id,
        "purpose": purpose,
        "requested_layers": requested_layers,
        "returned_layers": returned_layers,
        "feature_ids": feature_ids,
        "status": status,
        "reason": reason,
    }


def list_pcl_query_logs(app_id: Optional[str] = None, limit: int = 100) -> list[dict]:
    with get_connection() as conn:
        if app_id:
            rows = conn.execute(
                """SELECT * FROM pcl_query_logs
                   WHERE app_id = ?
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (app_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM pcl_query_logs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [
        {
            "id": row["id"],
            "app_id": row["app_id"],
            "user_id": row["user_id"],
            "purpose": row["purpose"],
            "requested_layers": json.loads(row["requested_layers"]),
            "returned_layers": json.loads(row["returned_layers"]),
            "feature_ids": json.loads(row["feature_ids"]),
            "status": row["status"],
            "reason": row["reason"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def clear_pcl_query_logs(app_id: Optional[str] = None, user_id: Optional[str] = None) -> int:
    clauses = []
    params = []
    if app_id:
        clauses.append("app_id = ?")
        params.append(app_id)
    if user_id:
        clauses.append("user_id = ?")
        params.append(user_id)

    query = "DELETE FROM pcl_query_logs"
    if clauses:
        query += " WHERE " + " AND ".join(clauses)

    with get_connection() as conn:
        count = conn.execute(query, tuple(params)).rowcount
        conn.commit()
    return count


def save_pcl_onboarding_seed(user_id: str, answers: dict, profile_seed: dict) -> dict:
    with get_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO pcl_onboarding_seeds
               (user_id, answers, profile_seed, updated_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)""",
            (user_id, json.dumps(answers), json.dumps(profile_seed)),
        )
        conn.commit()
    return get_pcl_onboarding_seed(user_id) or {}


def get_pcl_onboarding_seed(user_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM pcl_onboarding_seeds WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "user_id": row["user_id"],
        "answers": json.loads(row["answers"]),
        "profile_seed": json.loads(row["profile_seed"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def insert_pcl_feature_event(
    app_id: str,
    user_id: str,
    feature_id: str,
    feature_name: str,
    event_type: str,
    weight: float,
    metadata: dict,
    timestamp: int,
) -> dict:
    event_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO pcl_feature_events
               (id, app_id, user_id, feature_id, feature_name, event_type,
                weight, metadata, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event_id,
                app_id,
                user_id,
                feature_id,
                feature_name,
                event_type,
                float(weight),
                json.dumps(metadata),
                timestamp,
            ),
        )
        conn.commit()
    return {
        "id": event_id,
        "app_id": app_id,
        "user_id": user_id,
        "feature_id": feature_id,
        "feature_name": feature_name,
        "event_type": event_type,
        "weight": float(weight),
        "metadata": metadata,
        "timestamp": timestamp,
    }


def get_pcl_feature_usage(user_id: str, app_id: Optional[str] = None, days: int = 90) -> list[dict]:
    cutoff_ms = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
    with get_connection() as conn:
        if app_id:
            rows = conn.execute(
                """SELECT feature_id,
                          COALESCE(NULLIF(feature_name, ''), feature_id) as feature_name,
                          COUNT(*) as use_count,
                          MAX(timestamp) as last_used_at,
                          SUM(weight) as total_weight
                   FROM pcl_feature_events
                   WHERE user_id = ? AND app_id = ? AND timestamp >= ?
                   GROUP BY feature_id
                   ORDER BY total_weight DESC, last_used_at DESC""",
                (user_id, app_id, cutoff_ms),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT feature_id,
                          COALESCE(NULLIF(feature_name, ''), feature_id) as feature_name,
                          COUNT(*) as use_count,
                          MAX(timestamp) as last_used_at,
                          SUM(weight) as total_weight
                   FROM pcl_feature_events
                   WHERE user_id = ? AND timestamp >= ?
                   GROUP BY feature_id
                   ORDER BY total_weight DESC, last_used_at DESC""",
                (user_id, cutoff_ms),
            ).fetchall()
    return [
        {
            "feature_id": row["feature_id"],
            "feature_name": row["feature_name"],
            "use_count": row["use_count"],
            "last_used_at": row["last_used_at"],
            "total_weight": row["total_weight"],
        }
        for row in rows
    ]


def delete_pcl_user_data(user_id: str) -> dict:
    with get_connection() as conn:
        onboarding_seeds = conn.execute(
            "DELETE FROM pcl_onboarding_seeds WHERE user_id = ?",
            (user_id,),
        ).rowcount
        feature_events = conn.execute(
            "DELETE FROM pcl_feature_events WHERE user_id = ?",
            (user_id,),
        ).rowcount
        query_logs = conn.execute(
            "DELETE FROM pcl_query_logs WHERE user_id = ?",
            (user_id,),
        ).rowcount
        conn.commit()
    return {
        "user_id": user_id,
        "onboarding_seeds": onboarding_seeds,
        "feature_events": feature_events,
        "query_logs": query_logs,
    }


def connect_pcl_integration(
    source: str,
    name: str,
    scopes: list[str],
    metadata: Optional[dict] = None,
) -> dict:
    with get_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO pcl_integrations
               (source, name, status, scopes, metadata, disconnected_at)
               VALUES (?, ?, 'connected', ?, ?, NULL)""",
            (source, name, json.dumps(scopes), json.dumps(metadata or {})),
        )
        conn.commit()
    return get_pcl_integration(source) or {}


def get_pcl_integration(source: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM pcl_integrations WHERE source = ?",
            (source,),
        ).fetchone()
    if not row:
        return None
    return _pcl_integration_row(row)


def list_pcl_integrations() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM pcl_integrations ORDER BY connected_at DESC"
        ).fetchall()
    return [_pcl_integration_row(row) for row in rows]


def disconnect_pcl_integration(source: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            """UPDATE pcl_integrations
               SET status = 'disconnected', disconnected_at = CURRENT_TIMESTAMP
               WHERE source = ? AND status != 'disconnected'""",
            (source,),
        )
        conn.commit()
    return cursor.rowcount > 0


def delete_pcl_integration_data(source: str) -> dict:
    with get_connection() as conn:
        integrations = conn.execute(
            "DELETE FROM pcl_integrations WHERE source = ?",
            (source,),
        ).rowcount
        feed_items = conn.execute(
            "DELETE FROM feed_items WHERE source = ?",
            (source,),
        ).rowcount
        persona_signals = conn.execute(
            "DELETE FROM persona_signals WHERE source = ?",
            (source,),
        ).rowcount
        conn.commit()
    return {
        "source": source,
        "integrations": integrations,
        "feed_items": feed_items,
        "persona_signals": persona_signals,
    }


def update_pcl_integration_sync(
    source: str,
    status: str,
    items_synced: int = 0,
    error: str = "",
) -> dict:
    with get_connection() as conn:
        conn.execute(
            """UPDATE pcl_integrations
               SET last_sync_at = CURRENT_TIMESTAMP,
                   last_sync_status = ?,
                   items_synced = ?,
                   error = ?
               WHERE source = ?""",
            (status, int(items_synced), error[:500], source),
        )
        conn.commit()
    return get_pcl_integration(source) or {}


def _pcl_integration_row(row: sqlite3.Row) -> dict:
    return {
        "source": row["source"],
        "name": row["name"],
        "status": row["status"],
        "scopes": json.loads(row["scopes"]),
        "metadata": json.loads(row["metadata"]),
        "last_sync_at": row["last_sync_at"],
        "last_sync_status": row["last_sync_status"],
        "items_synced": row["items_synced"],
        "error": row["error"],
        "connected_at": row["connected_at"],
        "disconnected_at": row["disconnected_at"],
    }


def insert_raw_context_event(event: dict) -> dict:
    event_id = str(uuid.uuid4())
    now_ms = int(datetime.now().timestamp() * 1000)
    timestamp = int(event.get("timestamp") or now_ms)
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO raw_events
               (id, user_id, app_id, feature_id, action, session_id, source,
                is_synthetic, metadata, timestamp, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event_id,
                event["user_id"],
                event["app_id"],
                event["feature_id"],
                event["action"],
                event.get("session_id", ""),
                event.get("source", "sdk"),
                1 if event.get("is_synthetic") else 0,
                json.dumps(event.get("metadata", {})),
                timestamp,
                now_ms,
            ),
        )
        conn.commit()
    saved = {**event, "id": event_id, "timestamp": timestamp, "created_at": now_ms}
    upsert_feature_signal_from_event(saved)
    return saved


def log_privacy_filter_drop(event: dict, reason: str) -> dict:
    drop_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO privacy_filter_drops
               (id, user_id, app_id, feature_id, reason, source)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                drop_id,
                str(event.get("user_id", ""))[:120],
                str(event.get("app_id", ""))[:120],
                str(event.get("feature_id", ""))[:120],
                reason[:300],
                str(event.get("source", ""))[:80],
            ),
        )
        conn.commit()
    return {"id": drop_id, "reason": reason}


def list_privacy_filter_drops(user_id: Optional[str] = None, limit: int = 100) -> list[dict]:
    limit = max(1, min(int(limit), 500))
    query = "SELECT * FROM privacy_filter_drops"
    params: list[object] = []
    if user_id:
        query += " WHERE user_id = ?"
        params.append(user_id)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with get_connection() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    return [dict(row) for row in rows]


def upsert_feature_signal_from_event(event: dict) -> dict:
    delta = {
        "used": 0.10,
        "searched": 0.06,
        "skipped": -0.03,
        "dismissed": -0.08,
    }[event["action"]]
    usage_inc = 1 if event["action"] in {"used", "searched"} else 0
    skipped_inc = 1 if event["action"] == "skipped" else 0
    dismissed_inc = 1 if event["action"] == "dismissed" else 0
    namespace = f"{event['app_id']}:{event['feature_id']}"

    with get_connection() as conn:
        existing = conn.execute(
            """SELECT * FROM feature_signals
               WHERE user_id = ? AND app_id = ? AND feature_id = ?""",
            (event["user_id"], event["app_id"], event["feature_id"]),
        ).fetchone()
        if existing:
            score = max(0.0, min(1.0, float(existing["recency_score"]) + delta))
            conn.execute(
                """UPDATE feature_signals
                   SET usage_count = usage_count + ?,
                       skipped_count = skipped_count + ?,
                       dismissed_count = dismissed_count + ?,
                       last_used_at = ?,
                       recency_score = ?,
                       is_synthetic = CASE WHEN ? = 1 THEN is_synthetic ELSE 0 END,
                       is_active = 1,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE user_id = ? AND app_id = ? AND feature_id = ?""",
                (
                    usage_inc,
                    skipped_inc,
                    dismissed_inc,
                    event["timestamp"],
                    score,
                    1 if event.get("is_synthetic") else 0,
                    event["user_id"],
                    event["app_id"],
                    event["feature_id"],
                ),
            )
        else:
            conn.execute(
                """INSERT INTO feature_signals
                   (id, user_id, app_id, feature_id, namespace, usage_count,
                    skipped_count, dismissed_count, last_used_at, recency_score,
                    is_synthetic)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    event["user_id"],
                    event["app_id"],
                    event["feature_id"],
                    namespace,
                    usage_inc,
                    skipped_inc,
                    dismissed_inc,
                    event["timestamp"],
                    max(0.0, min(1.0, 0.3 if event.get("is_synthetic") else max(delta, 0.0))),
                    1 if event.get("is_synthetic") else 0,
                ),
            )
        conn.commit()
    return get_feature_signal(event["user_id"], event["app_id"], event["feature_id"]) or {}


def get_feature_signal(user_id: str, app_id: str, feature_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT * FROM feature_signals
               WHERE user_id = ? AND app_id = ? AND feature_id = ?""",
            (user_id, app_id, feature_id),
        ).fetchone()
    return _feature_signal_row(row) if row else None


def list_feature_signals(
    user_id: str,
    app_id: Optional[str] = None,
    active_only: bool = True,
) -> list[dict]:
    clauses = ["user_id = ?"]
    params: list[object] = [user_id]
    if app_id:
        clauses.append("app_id = ?")
        params.append(app_id)
    if active_only:
        clauses.append("is_active = 1")
    query = f"""
        SELECT * FROM feature_signals
        WHERE {' AND '.join(clauses)}
        ORDER BY recency_score DESC, last_used_at DESC
    """
    with get_connection() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    return [_feature_signal_row(row) for row in rows]


def update_feature_signal_scores(updates: list[tuple[str, float, float, int]]) -> None:
    with get_connection() as conn:
        for signal_id, recency_score, decay_score, is_active in updates:
            conn.execute(
                """UPDATE feature_signals
                   SET recency_score = ?, decay_score = ?, is_active = ?,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (recency_score, decay_score, is_active, signal_id),
            )
        conn.commit()


def delete_episodic_feature_signals(signal_ids: list[str]) -> int:
    if not signal_ids:
        return 0
    placeholders = ",".join("?" for _ in signal_ids)
    with get_connection() as conn:
        deleted = conn.execute(
            f"DELETE FROM feature_signals WHERE tier = 'episodic' AND id IN ({placeholders})",
            tuple(signal_ids),
        ).rowcount
        conn.commit()
    return deleted


def promote_episodic_feature_signals(user_id: Optional[str] = None) -> int:
    clauses = [
        "fs.tier = 'episodic'",
        "fs.usage_count >= 30",
        "fs.recency_score >= 0.85",
        "fs.is_active = 1",
    ]
    params: list[object] = []
    if user_id:
        clauses.append("fs.user_id = ?")
        params.append(user_id)
    where = " AND ".join(clauses)
    with get_connection() as conn:
        candidates = conn.execute(
            f"""SELECT fs.id
                FROM feature_signals fs
                JOIN raw_events re
                  ON re.user_id = fs.user_id
                 AND re.app_id = fs.app_id
                 AND re.feature_id = fs.feature_id
                WHERE {where}
                GROUP BY fs.id
                HAVING COUNT(DISTINCT NULLIF(re.session_id, '')) >= 5""",
            tuple(params),
        ).fetchall()
        ids = [row["id"] for row in candidates]
        if not ids:
            return 0
        placeholders = ",".join("?" for _ in ids)
        promoted = conn.execute(
            f"""UPDATE feature_signals
                SET tier = 'core', updated_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders})""",
            tuple(ids),
        ).rowcount
        conn.commit()
    return promoted


def demote_stale_core_feature_signals(now_ms: Optional[int] = None, user_id: Optional[str] = None) -> int:
    now_ms = now_ms or int(datetime.now().timestamp() * 1000)
    ninety_days_ms = 90 * 24 * 60 * 60 * 1000
    user_clause = " AND user_id = ?" if user_id else ""
    params = (now_ms - ninety_days_ms, user_id) if user_id else (now_ms - ninety_days_ms,)
    dismissed_params = (user_id,) if user_id else ()
    with get_connection() as conn:
        demoted_stale = conn.execute(
            f"""UPDATE feature_signals
               SET tier = 'episodic', updated_at = CURRENT_TIMESTAMP
               WHERE tier = 'core' AND last_used_at < ?{user_clause}""",
            params,
        ).rowcount
        demoted_dismissed = conn.execute(
            f"""UPDATE feature_signals
               SET tier = 'episodic', updated_at = CURRENT_TIMESTAMP
               WHERE tier = 'core' AND dismissed_count > 20{user_clause}""",
            dismissed_params,
        ).rowcount
        conn.commit()
    return demoted_stale + demoted_dismissed


def delete_old_raw_context_events(user_id: Optional[str] = None, older_than_ms: Optional[int] = None) -> int:
    older_than_ms = older_than_ms or int((datetime.now() - timedelta(days=7)).timestamp() * 1000)
    with get_connection() as conn:
        if user_id:
            deleted = conn.execute(
                "DELETE FROM raw_events WHERE user_id = ? AND created_at < ?",
                (user_id, older_than_ms),
            ).rowcount
        else:
            deleted = conn.execute(
                "DELETE FROM raw_events WHERE created_at < ?",
                (older_than_ms,),
            ).rowcount
        conn.commit()
    return deleted


def list_raw_context_events(user_id: str, days: int = 7) -> list[dict]:
    cutoff = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM raw_events
               WHERE user_id = ? AND created_at >= ?
               ORDER BY created_at DESC""",
            (user_id, cutoff),
        ).fetchall()
    return [_raw_context_event_row(row) for row in rows]


def save_context_bundle_record(
    bundle_id: str,
    user_id: str,
    app_id: str,
    feature_ids: list[str],
    expires_at: int,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO context_bundles
               (id, user_id, app_id, feature_ids, expires_at)
               VALUES (?, ?, ?, ?, ?)""",
            (bundle_id, user_id, app_id, json.dumps(feature_ids), expires_at),
        )
        conn.commit()


def get_context_bundle_record(bundle_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM context_bundles WHERE id = ?",
            (bundle_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "app_id": row["app_id"],
        "feature_ids": json.loads(row["feature_ids"]),
        "expires_at": row["expires_at"],
        "created_at": row["created_at"],
    }


def insert_context_feedback(
    user_id: str,
    bundle_id: str,
    app_id: str,
    outcome: str,
    features_actually_used: list[str],
) -> dict:
    feedback_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO feedback_events
               (id, user_id, bundle_id, app_id, outcome, features_actually_used)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                feedback_id,
                user_id,
                bundle_id,
                app_id,
                outcome,
                json.dumps(features_actually_used),
            ),
        )
        for feature_id in features_actually_used:
            conn.execute(
                """UPDATE feature_signals
                   SET recency_score = MIN(1.0, recency_score + 0.05),
                       updated_at = CURRENT_TIMESTAMP
                   WHERE user_id = ? AND app_id = ? AND feature_id = ?""",
                (user_id, app_id, feature_id),
            )
        bundle = get_context_bundle_record(bundle_id) or {"feature_ids": []}
        unused = set(bundle["feature_ids"]) - set(features_actually_used)
        for feature_id in unused:
            conn.execute(
                """UPDATE feature_signals
                   SET recency_score = MAX(0.0, recency_score - 0.01),
                       updated_at = CURRENT_TIMESTAMP
                   WHERE user_id = ? AND app_id = ? AND feature_id = ?""",
                (user_id, app_id, feature_id),
            )
        conn.commit()
    return {
        "id": feedback_id,
        "user_id": user_id,
        "bundle_id": bundle_id,
        "app_id": app_id,
        "outcome": outcome,
        "features_actually_used": features_actually_used,
    }


def save_active_context(
    user_id: str,
    project: str = "",
    active_apps: Optional[list[str]] = None,
    inferred_intent: str = "",
    session_depth: str = "shallow",
    ttl_seconds: int = 3600,
) -> dict:
    now_ms = int(datetime.now().timestamp() * 1000)
    expires_at = now_ms + max(60, int(ttl_seconds)) * 1000
    active_apps = active_apps or []
    if session_depth not in {"shallow", "moderate", "deep-work"}:
        session_depth = "shallow"
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT session_start FROM active_context WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        session_start = existing["session_start"] if existing else now_ms
        conn.execute(
            """INSERT OR REPLACE INTO active_context
               (user_id, project, active_apps, session_start, last_heartbeat,
                inferred_intent, session_depth, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                project[:200],
                json.dumps(active_apps[:20]),
                session_start,
                now_ms,
                inferred_intent[:120],
                session_depth,
                expires_at,
            ),
        )
        conn.commit()
    return get_active_context(user_id) or {}


def get_active_context(user_id: str) -> Optional[dict]:
    now_ms = int(datetime.now().timestamp() * 1000)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM active_context WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row and int(row["expires_at"]) <= now_ms:
            conn.execute("DELETE FROM active_context WHERE user_id = ?", (user_id,))
            conn.commit()
            return None
    if not row:
        return None
    return {
        "project": row["project"] or None,
        "active_apps": json.loads(row["active_apps"]),
        "session_start": row["session_start"],
        "last_heartbeat": row["last_heartbeat"],
        "inferred_intent": row["inferred_intent"] or None,
        "session_depth": row["session_depth"],
    }


def list_contextlayer_activity(user_id: str, limit: int = 100) -> dict:
    limit = max(1, min(int(limit), 500))
    with get_connection() as conn:
        raw = conn.execute(
            """SELECT app_id, feature_id, action, source, timestamp, created_at
               FROM raw_events
               WHERE user_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (user_id, limit),
        ).fetchall()
        queries = conn.execute(
            """SELECT app_id, purpose, requested_layers, returned_layers,
                      feature_ids, status, created_at
               FROM pcl_query_logs
               WHERE user_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (user_id, limit),
        ).fetchall()
        feedback = conn.execute(
            """SELECT bundle_id, app_id, outcome, features_actually_used, created_at
               FROM feedback_events
               WHERE user_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    return {
        "raw_events": [_raw_context_event_row(row) for row in raw],
        "query_log": [
            {
                **dict(row),
                "requested_layers": json.loads(row["requested_layers"]),
                "returned_layers": json.loads(row["returned_layers"]),
                "feature_ids": json.loads(row["feature_ids"]),
            }
            for row in queries
        ],
        "feedback_events": [
            {
                **dict(row),
                "features_actually_used": json.loads(row["features_actually_used"]),
            }
            for row in feedback
        ],
    }


def delete_contextlayer_user_data(user_id: str) -> dict:
    with get_connection() as conn:
        counts = {
            "feature_signals": conn.execute("DELETE FROM feature_signals WHERE user_id = ?", (user_id,)).rowcount,
            "raw_events": conn.execute("DELETE FROM raw_events WHERE user_id = ?", (user_id,)).rowcount,
            "query_log": conn.execute("DELETE FROM pcl_query_logs WHERE user_id = ?", (user_id,)).rowcount,
            "feedback_events": conn.execute("DELETE FROM feedback_events WHERE user_id = ?", (user_id,)).rowcount,
            "context_bundles": conn.execute("DELETE FROM context_bundles WHERE user_id = ?", (user_id,)).rowcount,
            "privacy_filter_drops": conn.execute("DELETE FROM privacy_filter_drops WHERE user_id = ?", (user_id,)).rowcount,
            "active_context": conn.execute("DELETE FROM active_context WHERE user_id = ?", (user_id,)).rowcount,
            "onboarding_seeds": conn.execute("DELETE FROM pcl_onboarding_seeds WHERE user_id = ?", (user_id,)).rowcount,
            "feature_events": conn.execute("DELETE FROM pcl_feature_events WHERE user_id = ?", (user_id,)).rowcount,
        }
        conn.commit()
    confirmation = str(uuid.uuid5(uuid.NAMESPACE_URL, f"contextlayer:{user_id}:{datetime.now().isoformat()}"))
    return {
        "deleted_at": datetime.now().isoformat(),
        "confirmation_hash": confirmation,
        "deleted": counts,
    }


def upsert_developer(email: str, name: str = "") -> dict:
    email = email.strip().lower()
    if not email:
        raise ValueError("email is required")
    developer_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"contextlayer:developer:{email}"))
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO developers (id, email, name)
               VALUES (?, ?, ?)
               ON CONFLICT(email) DO UPDATE SET name = excluded.name""",
            (developer_id, email, name.strip()),
        )
        conn.commit()
    return get_developer(developer_id) or {}


def get_developer(developer_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM developers WHERE id = ?",
            (developer_id,),
        ).fetchone()
    return dict(row) if row else None


def register_developer_app(
    developer_id: str,
    app_id: str,
    name: str,
    domain: str = "",
) -> dict:
    app_record_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"contextlayer:app:{app_id}"))
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO apps (id, developer_id, app_id, name, domain, is_active)
               VALUES (?, ?, ?, ?, ?, 1)
               ON CONFLICT(app_id) DO UPDATE SET
                 developer_id = excluded.developer_id,
                 name = excluded.name,
                 domain = excluded.domain,
                 is_active = 1""",
            (app_record_id, developer_id, app_id.strip(), name.strip() or app_id, domain.strip()),
        )
        conn.commit()
    return get_developer_app(app_id) or {}


def get_developer_app(app_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM apps WHERE app_id = ?",
            (app_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "developer_id": row["developer_id"],
        "app_id": row["app_id"],
        "name": row["name"],
        "domain": row["domain"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
    }


def create_developer_api_key(
    developer_id: str,
    app_id: str = "",
    env: str = "test",
) -> dict:
    raw_key = f"cl_{env}_{uuid.uuid4().hex}{uuid.uuid4().hex}"
    key_prefix = raw_key[:12]
    key_hash = str(uuid.uuid5(uuid.NAMESPACE_URL, raw_key))
    key_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO api_keys
               (id, developer_id, app_id, key_hash, key_prefix, env)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (key_id, developer_id, app_id, key_hash, key_prefix, env if env in {"test", "live"} else "test"),
        )
        conn.commit()
    return {
        **(get_developer_api_key(key_id) or {}),
        "key": raw_key,
    }


def verify_developer_api_key(raw_key: str) -> Optional[dict]:
    key_hash = str(uuid.uuid5(uuid.NAMESPACE_URL, raw_key.strip()))
    with get_connection() as conn:
        row = conn.execute(
            """SELECT * FROM api_keys
               WHERE key_hash = ? AND is_active = 1""",
            (key_hash,),
        ).fetchone()
        if not row:
            return None
        conn.execute(
            "UPDATE api_keys SET last_used_at = CURRENT_TIMESTAMP WHERE id = ?",
            (row["id"],),
        )
        conn.commit()
    return {
        "id": row["id"],
        "developer_id": row["developer_id"],
        "app_id": row["app_id"],
        "key_prefix": row["key_prefix"],
        "env": row["env"],
        "is_active": bool(row["is_active"]),
        "last_used_at": row["last_used_at"],
        "created_at": row["created_at"],
    }


def get_developer_api_key(key_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM api_keys WHERE id = ?",
            (key_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "developer_id": row["developer_id"],
        "app_id": row["app_id"],
        "key_prefix": row["key_prefix"],
        "env": row["env"],
        "is_active": bool(row["is_active"]),
        "last_used_at": row["last_used_at"],
        "created_at": row["created_at"],
    }


def list_developer_api_keys(developer_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM api_keys
               WHERE developer_id = ?
               ORDER BY created_at DESC""",
            (developer_id,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "developer_id": row["developer_id"],
            "app_id": row["app_id"],
            "key_prefix": row["key_prefix"],
            "env": row["env"],
            "is_active": bool(row["is_active"]),
            "last_used_at": row["last_used_at"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def grant_app_consent(
    user_id: str,
    app_id: str,
    scopes: Optional[list[str]] = None,
    developer_id: str = "",
    granted_via: str = "explicit",
) -> dict:
    permission_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"contextlayer:permission:{user_id}:{app_id}"))
    scopes = scopes or ["getFeatureUsage"]
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO app_permissions
               (id, user_id, app_id, developer_id, scopes, granted_via, is_active, revoked_at)
               VALUES (?, ?, ?, ?, ?, ?, 1, NULL)
               ON CONFLICT(user_id, app_id) DO UPDATE SET
                 developer_id = excluded.developer_id,
                 scopes = excluded.scopes,
                 granted_via = excluded.granted_via,
                 is_active = 1,
                 revoked_at = NULL,
                 granted_at = CURRENT_TIMESTAMP""",
            (permission_id, user_id, app_id, developer_id, json.dumps(scopes), granted_via),
        )
        conn.commit()
    return get_app_permission(user_id, app_id) or {}


def revoke_app_consent(user_id: str, app_id: str) -> bool:
    with get_connection() as conn:
        revoked = conn.execute(
            """UPDATE app_permissions
               SET is_active = 0, revoked_at = CURRENT_TIMESTAMP
               WHERE user_id = ? AND app_id = ? AND is_active = 1""",
            (user_id, app_id),
        ).rowcount
        conn.commit()
    return revoked > 0


def get_app_permission(user_id: str, app_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM app_permissions WHERE user_id = ? AND app_id = ?",
            (user_id, app_id),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "app_id": row["app_id"],
        "developer_id": row["developer_id"],
        "scopes": json.loads(row["scopes"]),
        "granted_via": row["granted_via"],
        "is_active": bool(row["is_active"]),
        "granted_at": row["granted_at"],
        "revoked_at": row["revoked_at"],
    }


def list_app_permissions(user_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM app_permissions
               WHERE user_id = ?
               ORDER BY granted_at DESC""",
            (user_id,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "user_id": row["user_id"],
            "app_id": row["app_id"],
            "developer_id": row["developer_id"],
            "scopes": json.loads(row["scopes"]),
            "granted_via": row["granted_via"],
            "is_active": bool(row["is_active"]),
            "granted_at": row["granted_at"],
            "revoked_at": row["revoked_at"],
        }
        for row in rows
    ]


def get_or_create_user_profile(user_id: str, timezone: str = "UTC") -> dict:
    now_ms = int(datetime.now().timestamp() * 1000)
    with get_connection() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO user_profiles
               (user_id, timezone, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)""",
            (user_id, timezone),
        )
        conn.commit()
    return get_user_profile_record(user_id) or {
        "user_id": user_id,
        "abstract_attributes": [],
        "context_brief": "",
        "daily_insight": "",
        "last_synthesized_at": None,
        "last_refresh_at": None,
        "timezone": timezone,
    }


def get_user_profile_record(user_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM user_profiles WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "user_id": row["user_id"],
        "abstract_attributes": json.loads(row["abstract_attributes"]),
        "context_brief": row["context_brief"],
        "daily_insight": row["daily_insight"],
        "last_synthesized_at": row["last_synthesized_at"],
        "last_refresh_at": row["last_refresh_at"],
        "timezone": row["timezone"],
        "updated_at": row["updated_at"],
    }


def list_user_profile_records() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM user_profiles ORDER BY updated_at DESC",
        ).fetchall()
    return [
        {
            "user_id": row["user_id"],
            "abstract_attributes": json.loads(row["abstract_attributes"]),
            "context_brief": row["context_brief"],
            "daily_insight": row["daily_insight"],
            "last_synthesized_at": row["last_synthesized_at"],
            "last_refresh_at": row["last_refresh_at"],
            "timezone": row["timezone"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def update_user_profile_record(
    user_id: str,
    abstract_attributes: Optional[list[dict]] = None,
    context_brief: Optional[str] = None,
    daily_insight: Optional[str] = None,
    last_synthesized_at: Optional[int] = None,
    last_refresh_at: Optional[int] = None,
    timezone: Optional[str] = None,
) -> dict:
    get_or_create_user_profile(user_id, timezone or "UTC")
    updates = []
    params: list[object] = []
    if abstract_attributes is not None:
        updates.append("abstract_attributes = ?")
        params.append(json.dumps(abstract_attributes))
    if context_brief is not None:
        updates.append("context_brief = ?")
        params.append(context_brief[:4000])
    if daily_insight is not None:
        updates.append("daily_insight = ?")
        params.append(daily_insight[:500])
    if last_synthesized_at is not None:
        updates.append("last_synthesized_at = ?")
        params.append(int(last_synthesized_at))
    if last_refresh_at is not None:
        updates.append("last_refresh_at = ?")
        params.append(int(last_refresh_at))
    if timezone is not None:
        updates.append("timezone = ?")
        params.append(timezone[:80])
    if updates:
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(user_id)
        with get_connection() as conn:
            conn.execute(
                f"UPDATE user_profiles SET {', '.join(updates)} WHERE user_id = ?",
                tuple(params),
            )
            conn.commit()
    return get_user_profile_record(user_id) or {}


def create_or_resume_daily_refresh_job(
    user_id: str,
    timezone: str = "UTC",
    job_id: Optional[str] = None,
    step_completed: int = 0,
) -> dict:
    now_ms = int(datetime.now().timestamp() * 1000)
    job_id = job_id or str(uuid.uuid4())
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM daily_refresh_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if not existing:
            conn.execute(
                """INSERT INTO daily_refresh_jobs
                   (id, user_id, timezone, step_completed, status, started_at, updated_at)
                   VALUES (?, ?, ?, ?, 'running', ?, ?)""",
                (job_id, user_id, timezone, int(step_completed), now_ms, now_ms),
            )
        conn.commit()
    return get_daily_refresh_job(job_id) or {}


def list_daily_refresh_jobs(user_id: Optional[str] = None, limit: int = 100) -> list[dict]:
    query = "SELECT * FROM daily_refresh_jobs"
    params: list[object] = []
    if user_id:
        query += " WHERE user_id = ?"
        params.append(user_id)
    query += " ORDER BY updated_at DESC LIMIT ?"
    params.append(max(1, min(int(limit), 500)))
    with get_connection() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    return [dict(row) for row in rows]


def get_daily_refresh_job(job_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM daily_refresh_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
    return dict(row) if row else None


def update_daily_refresh_step(job_id: str, step_completed: int) -> dict:
    now_ms = int(datetime.now().timestamp() * 1000)
    with get_connection() as conn:
        conn.execute(
            """UPDATE daily_refresh_jobs
               SET step_completed = ?, updated_at = ?, status = 'running'
               WHERE id = ?""",
            (int(step_completed), now_ms, job_id),
        )
        conn.commit()
    return get_daily_refresh_job(job_id) or {}


def mark_daily_refresh_complete(job_id: str, user_id: str) -> dict:
    now_ms = int(datetime.now().timestamp() * 1000)
    with get_connection() as conn:
        conn.execute(
            """UPDATE daily_refresh_jobs
               SET step_completed = 11, status = 'complete',
                   completed_at = ?, last_refresh_at = ?, updated_at = ?
               WHERE id = ?""",
            (now_ms, now_ms, now_ms, job_id),
        )
        conn.commit()
    update_user_profile_record(user_id, last_refresh_at=now_ms)
    return get_daily_refresh_job(job_id) or {}


def mark_daily_refresh_failed(job_id: str, error: str) -> dict:
    now_ms = int(datetime.now().timestamp() * 1000)
    with get_connection() as conn:
        conn.execute(
            """UPDATE daily_refresh_jobs
               SET status = 'failed', error = ?, updated_at = ?
               WHERE id = ?""",
            (error[:500], now_ms, job_id),
        )
        conn.commit()
    return get_daily_refresh_job(job_id) or {}


def insert_daily_refresh_step_log(
    job_id: str,
    user_id: str,
    step_number: int,
    step_name: str,
    status: str,
    error: str = "",
) -> dict:
    log_id = str(uuid.uuid4())
    now_ms = int(datetime.now().timestamp() * 1000)
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO daily_refresh_step_logs
               (id, job_id, user_id, step_number, step_name, status, error, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (log_id, job_id, user_id, step_number, step_name, status, error[:500], now_ms),
        )
        conn.commit()
    return {
        "id": log_id,
        "job_id": job_id,
        "user_id": user_id,
        "step_number": step_number,
        "step_name": step_name,
        "status": status,
        "error": error[:500],
        "created_at": now_ms,
    }


def list_daily_refresh_step_logs(job_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM daily_refresh_step_logs
               WHERE job_id = ?
               ORDER BY step_number ASC, created_at ASC""",
            (job_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def _feature_signal_row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "app_id": row["app_id"],
        "feature_id": row["feature_id"],
        "namespace": row["namespace"],
        "usage_count": row["usage_count"],
        "skipped_count": row["skipped_count"],
        "dismissed_count": row["dismissed_count"],
        "last_used_at": row["last_used_at"],
        "recency_score": row["recency_score"],
        "decay_score": row["decay_score"],
        "tier": row["tier"],
        "abstract_attributes": json.loads(row["abstract_attributes"]),
        "is_synthetic": bool(row["is_synthetic"]),
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _raw_context_event_row(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["metadata"] = json.loads(data.get("metadata") or "{}")
    data["is_synthetic"] = bool(data.get("is_synthetic"))
    return data
