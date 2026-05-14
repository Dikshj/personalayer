import hashlib
import hmac
import sqlite3
import base64
import json
import math
import os
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
                sync_cursor TEXT DEFAULT '{}',
                next_sync_after INTEGER,
                account_hint TEXT DEFAULT '',
                auth_status TEXT DEFAULT 'local_metadata',
                auth_expires_at INTEGER,
                error TEXT DEFAULT '',
                connected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                disconnected_at DATETIME
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pcl_integration_oauth_states (
                state TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                user_id TEXT NOT NULL,
                redirect_uri TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                code_verifier TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                consumed_at DATETIME
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pcl_integration_oauth_tokens (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                user_id TEXT NOT NULL,
                account_hint TEXT DEFAULT '',
                encrypted_token_blob TEXT NOT NULL,
                token_fingerprint TEXT NOT NULL,
                scopes TEXT DEFAULT '[]',
                expires_at INTEGER,
                has_refresh_token INTEGER DEFAULT 0,
                token_type TEXT DEFAULT 'Bearer',
                status TEXT DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                revoked_at DATETIME,
                UNIQUE(source, user_id)
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
            CREATE TABLE IF NOT EXISTS web_domain_permissions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                scopes TEXT DEFAULT '["getFeatureUsage"]',
                is_active INTEGER DEFAULT 1,
                granted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                revoked_at DATETIME,
                UNIQUE(user_id, domain)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS push_tokens (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                device_id TEXT NOT NULL,
                apns_token TEXT NOT NULL,
                platform TEXT DEFAULT 'ios',
                environment TEXT DEFAULT 'development',
                is_active INTEGER DEFAULT 1,
                registered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                revoked_at DATETIME,
                UNIQUE(user_id, device_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notification_routes (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                device_id TEXT NOT NULL,
                push_token_id TEXT NOT NULL,
                notification_type TEXT NOT NULL,
                deliver_after INTEGER NOT NULL,
                payload_kind TEXT DEFAULT 'silent_local_insight',
                status TEXT DEFAULT 'queued',
                created_at INTEGER NOT NULL
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kg_nodes (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('app','concept','project','person','feature','place')),
                label TEXT NOT NULL,
                embedding BLOB,
                tier TEXT DEFAULT 'hot' CHECK(tier IN ('hot','warm','cool','cold')),
                decay_score REAL DEFAULT 1.0,
                access_count INTEGER DEFAULT 0,
                first_seen INTEGER NOT NULL,
                last_seen INTEGER NOT NULL,
                compressed INTEGER DEFAULT 0,
                UNIQUE(user_id, type, label)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kg_edges (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                from_node TEXT NOT NULL,
                to_node TEXT NOT NULL,
                relation TEXT NOT NULL CHECK(relation IN ('used','mentions','relates_to','happened_at','created','skipped')),
                weight REAL DEFAULT 1.0,
                source_app TEXT DEFAULT '',
                timestamp INTEGER NOT NULL,
                tier TEXT DEFAULT 'hot' CHECK(tier IN ('hot','warm','cool','cold')),
                UNIQUE(user_id, from_node, to_node, relation, source_app)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS temporal_chains (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                source TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                context_hash TEXT NOT NULL
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
        oauth_tokens = conn.execute(
            "DELETE FROM pcl_integration_oauth_tokens WHERE user_id = ?",
            (user_id,),
        ).rowcount
        oauth_states = conn.execute(
            "DELETE FROM pcl_integration_oauth_states WHERE user_id = ?",
            (user_id,),
        ).rowcount
        conn.commit()
    return {
        "user_id": user_id,
        "onboarding_seeds": onboarding_seeds,
        "feature_events": feature_events,
        "query_logs": query_logs,
        "oauth_tokens": oauth_tokens,
        "oauth_states": oauth_states,
    }


def connect_pcl_integration(
    source: str,
    name: str,
    scopes: list[str],
    metadata: Optional[dict] = None,
    account_hint: str = "",
    auth_status: str = "local_metadata",
    auth_expires_at: Optional[int] = None,
) -> dict:
    with get_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO pcl_integrations
               (source, name, status, scopes, metadata, account_hint, auth_status,
                auth_expires_at, disconnected_at)
               VALUES (?, ?, 'connected', ?, ?, ?, ?, ?, NULL)""",
            (
                source,
                name,
                json.dumps(scopes),
                json.dumps(metadata or {}),
                account_hint[:240],
                auth_status[:80],
                auth_expires_at,
            ),
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
        oauth_states = conn.execute(
            "DELETE FROM pcl_integration_oauth_states WHERE source = ?",
            (source,),
        ).rowcount
        oauth_tokens = conn.execute(
            "DELETE FROM pcl_integration_oauth_tokens WHERE source = ?",
            (source,),
        ).rowcount
        conn.commit()
    return {
        "source": source,
        "integrations": integrations,
        "feed_items": feed_items,
        "persona_signals": persona_signals,
        "oauth_states": oauth_states,
        "oauth_tokens": oauth_tokens,
    }


def create_pcl_integration_oauth_state(
    source: str,
    user_id: str,
    redirect_uri: str,
    code_verifier: str = "",
) -> dict:
    state = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO pcl_integration_oauth_states
               (state, source, user_id, redirect_uri, code_verifier)
               VALUES (?, ?, ?, ?, ?)""",
            (state, source, user_id, redirect_uri, code_verifier),
        )
        conn.commit()
    return get_pcl_integration_oauth_state(state) or {}


def get_pcl_integration_oauth_state(state: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM pcl_integration_oauth_states WHERE state = ?",
            (state,),
        ).fetchone()
    if not row:
        return None
    return {
        "state": row["state"],
        "source": row["source"],
        "user_id": row["user_id"],
        "redirect_uri": row["redirect_uri"],
        "status": row["status"],
        "code_verifier": row["code_verifier"],
        "created_at": row["created_at"],
        "consumed_at": row["consumed_at"],
    }


def consume_pcl_integration_oauth_state(state: str) -> Optional[dict]:
    current = get_pcl_integration_oauth_state(state)
    if not current or current["status"] != "pending":
        return None
    with get_connection() as conn:
        conn.execute(
            """UPDATE pcl_integration_oauth_states
               SET status = 'consumed', consumed_at = CURRENT_TIMESTAMP
               WHERE state = ? AND status = 'pending'""",
            (state,),
        )
        conn.commit()
    return get_pcl_integration_oauth_state(state)


def store_pcl_integration_oauth_token(
    source: str,
    user_id: str,
    token_payload: dict,
    account_hint: str = "",
    scopes: Optional[list[str]] = None,
    expires_at: Optional[int] = None,
) -> dict:
    access_token = str(token_payload.get("access_token") or "")
    refresh_token = str(token_payload.get("refresh_token") or "")
    if not access_token:
        raise ValueError("access_token is required")
    token_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"contextlayer:integration-token:{source}:{user_id}"))
    encrypted = _encrypt_local_secret_blob({
        **token_payload,
        "source": source,
        "user_id": user_id,
    })
    fingerprint = hmac.new(
        _local_secret_key(),
        access_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO pcl_integration_oauth_tokens
               (id, source, user_id, account_hint, encrypted_token_blob,
                token_fingerprint, scopes, expires_at, has_refresh_token,
                token_type, status, revoked_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', NULL)
               ON CONFLICT(source, user_id) DO UPDATE SET
                 account_hint = excluded.account_hint,
                 encrypted_token_blob = excluded.encrypted_token_blob,
                 token_fingerprint = excluded.token_fingerprint,
                 scopes = excluded.scopes,
                 expires_at = excluded.expires_at,
                 has_refresh_token = excluded.has_refresh_token,
                 token_type = excluded.token_type,
                 status = 'active',
                 updated_at = CURRENT_TIMESTAMP,
                 revoked_at = NULL""",
            (
                token_id,
                source,
                user_id,
                account_hint[:240],
                encrypted,
                fingerprint,
                json.dumps(_normalize_oauth_scopes(scopes or token_payload.get("scope", []))),
                expires_at or token_payload.get("expires_at"),
                1 if refresh_token else 0,
                str(token_payload.get("token_type") or "Bearer")[:40],
            ),
        )
        conn.commit()
    return get_pcl_integration_oauth_token(source=source, user_id=user_id) or {}


def get_pcl_integration_oauth_token(source: str, user_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT * FROM pcl_integration_oauth_tokens
               WHERE source = ? AND user_id = ?""",
            (source, user_id),
        ).fetchone()
    return _pcl_integration_oauth_token_row(row) if row else None


def get_decrypted_pcl_integration_oauth_token(source: str, user_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT encrypted_token_blob FROM pcl_integration_oauth_tokens
               WHERE source = ? AND user_id = ? AND status = 'active'""",
            (source, user_id),
        ).fetchone()
    if not row:
        return None
    return _decrypt_local_secret_blob(row["encrypted_token_blob"])


def list_pcl_integration_oauth_tokens(user_id: str = "local_user") -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM pcl_integration_oauth_tokens
               WHERE user_id = ?
               ORDER BY updated_at DESC""",
            (user_id,),
        ).fetchall()
    return [_pcl_integration_oauth_token_row(row) for row in rows]


def revoke_pcl_integration_oauth_token(source: str, user_id: str = "local_user") -> bool:
    with get_connection() as conn:
        revoked = conn.execute(
            """UPDATE pcl_integration_oauth_tokens
               SET status = 'revoked', revoked_at = CURRENT_TIMESTAMP
               WHERE source = ? AND user_id = ? AND status = 'active'""",
            (source, user_id),
        ).rowcount
        conn.commit()
    return revoked > 0


def update_pcl_integration_sync(
    source: str,
    status: str,
    items_synced: int = 0,
    error: str = "",
    sync_cursor: Optional[dict] = None,
    next_sync_after: Optional[int] = None,
) -> dict:
    cursor_json = json.dumps(sync_cursor or {})
    with get_connection() as conn:
        if sync_cursor is None and next_sync_after is None:
            conn.execute(
                """UPDATE pcl_integrations
                   SET last_sync_at = CURRENT_TIMESTAMP,
                       last_sync_status = ?,
                       items_synced = ?,
                       error = ?
                   WHERE source = ?""",
                (status, int(items_synced), error[:500], source),
            )
        elif next_sync_after is None:
            conn.execute(
                """UPDATE pcl_integrations
                   SET last_sync_at = CURRENT_TIMESTAMP,
                       last_sync_status = ?,
                       items_synced = ?,
                       sync_cursor = ?,
                       error = ?
                   WHERE source = ?""",
                (status, int(items_synced), cursor_json, error[:500], source),
            )
        else:
            conn.execute(
                """UPDATE pcl_integrations
                   SET last_sync_at = CURRENT_TIMESTAMP,
                       last_sync_status = ?,
                       items_synced = ?,
                       sync_cursor = ?,
                       next_sync_after = ?,
                       error = ?
                   WHERE source = ?""",
                (status, int(items_synced), cursor_json, int(next_sync_after), error[:500], source),
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
        "sync_cursor": json.loads(row["sync_cursor"] or "{}"),
        "next_sync_after": row["next_sync_after"],
        "account_hint": row["account_hint"],
        "auth_status": row["auth_status"],
        "auth_expires_at": row["auth_expires_at"],
        "error": row["error"],
        "connected_at": row["connected_at"],
        "disconnected_at": row["disconnected_at"],
    }


def _pcl_integration_oauth_token_row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "source": row["source"],
        "user_id": row["user_id"],
        "account_hint": row["account_hint"],
        "token_fingerprint": row["token_fingerprint"][:16],
        "scopes": json.loads(row["scopes"] or "[]"),
        "expires_at": row["expires_at"],
        "has_refresh_token": bool(row["has_refresh_token"]),
        "token_type": row["token_type"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "revoked_at": row["revoked_at"],
    }


def _normalize_oauth_scopes(scopes: object) -> list[str]:
    if isinstance(scopes, str):
        return [scope for scope in scopes.split() if scope]
    if isinstance(scopes, list):
        return [str(scope) for scope in scopes if str(scope).strip()]
    return []


def _local_secret_key() -> bytes:
    DATA_DIR.mkdir(exist_ok=True)
    key_path = DATA_DIR / "local_secret.key"
    if not key_path.exists():
        key_path.write_bytes(os.urandom(32))
    return key_path.read_bytes()[:32].ljust(32, b"\0")


def _encrypt_local_secret_blob(payload: dict) -> str:
    plaintext = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    key = _local_secret_key()
    cipher = bytes(byte ^ key[index % len(key)] for index, byte in enumerate(plaintext))
    mac = hmac.new(key, cipher, hashlib.sha256).hexdigest()
    return json.dumps({
        "version": 1,
        "ciphertext": base64.b64encode(cipher).decode("ascii"),
        "mac": mac,
    }, separators=(",", ":"))


def _decrypt_local_secret_blob(envelope_json: str) -> dict:
    envelope = json.loads(envelope_json)
    key = _local_secret_key()
    cipher = base64.b64decode(envelope["ciphertext"])
    expected = hmac.new(key, cipher, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, envelope.get("mac", "")):
        raise ValueError("local secret blob failed integrity check")
    plaintext = bytes(byte ^ key[index % len(key)] for index, byte in enumerate(cipher))
    return json.loads(plaintext.decode("utf-8"))


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


def ingest_knowledge_graph_event(event: dict) -> dict:
    user_id = event["user_id"]
    timestamp = int(event["timestamp"])
    app_node = upsert_kg_node(user_id, "app", event["app_id"], timestamp)
    feature_node = upsert_kg_node(user_id, "feature", event["feature_id"], timestamp)
    relation = "skipped" if event["action"] in {"skipped", "dismissed"} else "used"
    edge = upsert_kg_edge(
        user_id=user_id,
        from_node=app_node["id"],
        to_node=feature_node["id"],
        relation=relation,
        source_app=event["app_id"],
        timestamp=timestamp,
    )
    nodes = [app_node, feature_node]
    metadata = event.get("metadata", {})
    category = metadata.get("subject_category") if isinstance(metadata, dict) else ""
    if category:
        concept_node = upsert_kg_node(user_id, "concept", category, timestamp)
        upsert_kg_edge(
            user_id=user_id,
            from_node=feature_node["id"],
            to_node=concept_node["id"],
            relation="relates_to",
            source_app=event["app_id"],
            timestamp=timestamp,
        )
        nodes.append(concept_node)
    chain = insert_temporal_chain(
        user_id=user_id,
        entity_id=feature_node["id"],
        timestamp=timestamp,
        source=event.get("source", "sdk"),
        signal_type=event["action"],
        context_hash=_context_hash(event),
    )
    return {"nodes": nodes, "edge": edge, "temporal_chain": chain}


def upsert_kg_node(
    user_id: str,
    node_type: str,
    label: str,
    timestamp: int,
    embedding: bytes | None = None,
) -> dict:
    clean_label = str(label).strip().lower()[:200]
    embedding = embedding or _embed_kg_label(clean_label)
    matched = _find_similar_kg_node(user_id, node_type, embedding)
    if matched:
        with get_connection() as conn:
            conn.execute(
                """UPDATE kg_nodes
                   SET access_count = access_count + 1,
                       last_seen = ?,
                       tier = CASE WHEN tier = 'cold' THEN 'warm' ELSE tier END,
                       decay_score = MIN(1.0, decay_score + 0.05)
                   WHERE id = ?""",
                (timestamp, matched["id"]),
            )
            conn.commit()
        return get_kg_node_by_id(matched["id"]) or matched

    node_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"contextlayer:kg:{user_id}:{node_type}:{clean_label}"))
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO kg_nodes
               (id, user_id, type, label, embedding, tier, decay_score, access_count,
                first_seen, last_seen, compressed)
               VALUES (?, ?, ?, ?, ?, 'hot', 1.0, 1, ?, ?, 0)
               ON CONFLICT(user_id, type, label) DO UPDATE SET
                   access_count = access_count + 1,
                   last_seen = excluded.last_seen,
                   tier = CASE WHEN kg_nodes.tier = 'cold' THEN 'warm' ELSE kg_nodes.tier END,
                   decay_score = MIN(1.0, kg_nodes.decay_score + 0.05)""",
            (node_id, user_id, node_type, clean_label, embedding, timestamp, timestamp),
        )
        conn.commit()
    return get_kg_node(user_id, node_type, clean_label) or {}


def get_kg_node_by_id(node_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM kg_nodes WHERE id = ?", (node_id,)).fetchone()
    return _kg_node_row(row) if row else None


def get_kg_node(user_id: str, node_type: str, label: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM kg_nodes WHERE user_id = ? AND type = ? AND label = ?",
            (user_id, node_type, str(label).strip().lower()[:200]),
        ).fetchone()
    return _kg_node_row(row) if row else None


def upsert_kg_edge(
    user_id: str,
    from_node: str,
    to_node: str,
    relation: str,
    source_app: str,
    timestamp: int,
) -> dict:
    edge_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"contextlayer:kg-edge:{user_id}:{from_node}:{to_node}:{relation}:{source_app}"))
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO kg_edges
               (id, user_id, from_node, to_node, relation, weight, source_app, timestamp, tier)
               VALUES (?, ?, ?, ?, ?, 1.0, ?, ?, 'hot')
               ON CONFLICT(user_id, from_node, to_node, relation, source_app) DO UPDATE SET
                   weight = weight + 1.0,
                   timestamp = excluded.timestamp,
                   tier = CASE WHEN kg_edges.tier = 'cold' THEN 'warm' ELSE kg_edges.tier END""",
            (edge_id, user_id, from_node, to_node, relation, source_app, timestamp),
        )
        conn.commit()
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM kg_edges WHERE id = ?", (edge_id,)).fetchone()
    return _kg_edge_row(row) if row else {}


def insert_temporal_chain(
    user_id: str,
    entity_id: str,
    timestamp: int,
    source: str,
    signal_type: str,
    context_hash: str,
) -> dict:
    chain_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO temporal_chains
               (id, user_id, entity_id, timestamp, source, signal_type, context_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (chain_id, user_id, entity_id, timestamp, source, signal_type, context_hash),
        )
        conn.commit()
    return {
        "id": chain_id,
        "user_id": user_id,
        "entity_id": entity_id,
        "timestamp": timestamp,
        "source": source,
        "signal_type": signal_type,
        "context_hash": context_hash,
    }


def list_kg_nodes(user_id: str, limit: int = 100) -> list[dict]:
    limit = max(1, min(int(limit), 500))
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM kg_nodes
               WHERE user_id = ?
               ORDER BY last_seen DESC
               LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    return [_kg_node_row(row) for row in rows]


def _find_similar_kg_node(user_id: str, node_type: str, embedding: bytes, threshold: float = 0.92) -> Optional[dict]:
    from pcl.embeddings import cosine_similarity, deserialize_embedding

    candidate = deserialize_embedding(embedding)
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM kg_nodes WHERE user_id = ? AND type = ? AND embedding IS NOT NULL",
            (user_id, node_type),
        ).fetchall()
    best_row = None
    best_score = 0.0
    for row in rows:
        score = cosine_similarity(candidate, deserialize_embedding(row["embedding"]))
        if score > best_score:
            best_score = score
            best_row = row
    if best_row and best_score >= threshold:
        result = _kg_node_row(best_row)
        result["similarity"] = round(best_score, 4)
        return result
    return None


def _embed_kg_label(label: str) -> bytes:
    from pcl.embeddings import embed_label, serialize_embedding

    return serialize_embedding(embed_label(label))


def list_kg_edges(user_id: str, limit: int = 100) -> list[dict]:
    limit = max(1, min(int(limit), 500))
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM kg_edges
               WHERE user_id = ?
               ORDER BY timestamp DESC
               LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    return [_kg_edge_row(row) for row in rows]


def list_temporal_chains(user_id: str, limit: int = 100) -> list[dict]:
    limit = max(1, min(int(limit), 500))
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM temporal_chains
               WHERE user_id = ?
               ORDER BY timestamp DESC
               LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def maintain_knowledge_graph_tiers(user_id: str, now_ms: Optional[int] = None) -> dict:
    now_ms = now_ms or int(datetime.now().timestamp() * 1000)
    day_ms = 86_400_000
    hot_cutoff = now_ms - (2 * day_ms)
    warm_cutoff = now_ms - (14 * day_ms)
    cool_cutoff = now_ms - (90 * day_ms)
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, label, tier, decay_score, last_seen FROM kg_nodes WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        hot_labels = {
            row["label"]
            for row in rows
            if row["tier"] == "hot" and int(row["last_seen"]) >= hot_cutoff
        }
        updates: list[tuple[str, float, int, str]] = []
        reactivated = 0
        for row in rows:
            tier = row["tier"]
            last_seen = int(row["last_seen"])
            days_since = max(0.0, (now_ms - last_seen) / day_ms)
            score = float(row["decay_score"])
            next_tier = tier
            compressed = 1 if tier in {"cool", "cold"} else 0

            if tier == "warm":
                score = max(0.0, score * math.exp(-0.02 * days_since))
            elif tier == "cool":
                score = max(0.0, score * math.exp(-0.06 * days_since))

            if tier == "hot" and last_seen < hot_cutoff:
                next_tier = "warm"
            elif tier == "warm" and (last_seen < warm_cutoff or score < 0.01):
                next_tier = "cool"
            elif tier == "warm" and score < 0.05:
                next_tier = "cool"
            elif tier == "cool" and last_seen < cool_cutoff:
                next_tier = "cold"

            if next_tier in {"cool", "cold"}:
                compressed = 1

            if next_tier in {"cool", "cold"} and _kg_context_cue_matches(row["label"], hot_labels):
                next_tier = "warm"
                compressed = 0
                score = max(score, 0.25)
                reactivated += 1

            updates.append((next_tier, round(score, 4), compressed, row["id"]))

        for tier, score, compressed, node_id in updates:
            conn.execute(
                """UPDATE kg_nodes
                   SET tier = ?, decay_score = ?, compressed = ?
                   WHERE id = ?""",
                (tier, score, compressed, node_id),
            )
        conn.commit()
    return {
        "updated": len(updates),
        "reactivated": reactivated,
        "hot": sum(1 for tier, _, _, _ in updates if tier == "hot"),
        "warm": sum(1 for tier, _, _, _ in updates if tier == "warm"),
        "cool": sum(1 for tier, _, _, _ in updates if tier == "cool"),
        "cold": sum(1 for tier, _, _, _ in updates if tier == "cold"),
    }


def delete_old_temporal_chains(user_id: Optional[str] = None, older_than_ms: Optional[int] = None) -> int:
    older_than_ms = older_than_ms or int((datetime.now() - timedelta(days=7)).timestamp() * 1000)
    with get_connection() as conn:
        if user_id:
            deleted = conn.execute(
                "DELETE FROM temporal_chains WHERE user_id = ? AND timestamp < ?",
                (user_id, older_than_ms),
            ).rowcount
        else:
            deleted = conn.execute(
                "DELETE FROM temporal_chains WHERE timestamp < ?",
                (older_than_ms,),
            ).rowcount
        conn.commit()
    return deleted


def _kg_context_cue_matches(label: str, hot_labels: set[str]) -> bool:
    label_tokens = {token for token in str(label).replace("-", " ").split() if len(token) >= 4}
    if not label_tokens:
        return False
    for hot_label in hot_labels:
        hot_tokens = {token for token in str(hot_label).replace("-", " ").split() if len(token) >= 4}
        if label_tokens & hot_tokens:
            return True
    return False


def _context_hash(event: dict) -> str:
    payload = {
        "app_id": event.get("app_id", ""),
        "feature_id": event.get("feature_id", ""),
        "source": event.get("source", ""),
        "session_id": event.get("session_id", ""),
        "metadata": event.get("metadata", {}),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _kg_node_row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "type": row["type"],
        "label": row["label"],
        "embedding": row["embedding"],
        "tier": row["tier"],
        "decay_score": row["decay_score"],
        "access_count": row["access_count"],
        "first_seen": row["first_seen"],
        "last_seen": row["last_seen"],
        "compressed": bool(row["compressed"]),
    }


def _kg_edge_row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "from_node": row["from_node"],
        "to_node": row["to_node"],
        "relation": row["relation"],
        "weight": row["weight"],
        "source_app": row["source_app"],
        "timestamp": row["timestamp"],
        "tier": row["tier"],
    }


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
        nodes = conn.execute(
            """SELECT * FROM kg_nodes
               WHERE user_id = ?
               ORDER BY last_seen DESC
               LIMIT ?""",
            (user_id, limit),
        ).fetchall()
        temporal = conn.execute(
            """SELECT * FROM temporal_chains
               WHERE user_id = ?
               ORDER BY timestamp DESC
               LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    return {
        "raw_events": [_raw_context_event_row(row) for row in raw],
        "knowledge_graph": {
            "nodes": [_kg_node_row(row) for row in nodes],
            "temporal_chains": [dict(row) for row in temporal],
        },
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
            "kg_nodes": conn.execute("DELETE FROM kg_nodes WHERE user_id = ?", (user_id,)).rowcount,
            "kg_edges": conn.execute("DELETE FROM kg_edges WHERE user_id = ?", (user_id,)).rowcount,
            "temporal_chains": conn.execute("DELETE FROM temporal_chains WHERE user_id = ?", (user_id,)).rowcount,
            "web_domain_permissions": conn.execute("DELETE FROM web_domain_permissions WHERE user_id = ?", (user_id,)).rowcount,
            "push_tokens": conn.execute("DELETE FROM push_tokens WHERE user_id = ?", (user_id,)).rowcount,
            "notification_routes": conn.execute("DELETE FROM notification_routes WHERE user_id = ?", (user_id,)).rowcount,
            "oauth_tokens": conn.execute("DELETE FROM pcl_integration_oauth_tokens WHERE user_id = ?", (user_id,)).rowcount,
            "oauth_states": conn.execute("DELETE FROM pcl_integration_oauth_states WHERE user_id = ?", (user_id,)).rowcount,
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


def grant_web_domain_permission(
    user_id: str,
    domain: str,
    scopes: Optional[list[str]] = None,
) -> dict:
    clean_domain = _normalize_web_domain(domain)
    permission_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"contextlayer:web-permission:{user_id}:{clean_domain}"))
    scopes = scopes or ["getFeatureUsage", "track"]
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO web_domain_permissions
               (id, user_id, domain, scopes, is_active, revoked_at)
               VALUES (?, ?, ?, ?, 1, NULL)
               ON CONFLICT(user_id, domain) DO UPDATE SET
                 scopes = excluded.scopes,
                 is_active = 1,
                 revoked_at = NULL,
                 granted_at = CURRENT_TIMESTAMP""",
            (permission_id, user_id, clean_domain, json.dumps(scopes)),
        )
        conn.commit()
    return get_web_domain_permission(user_id, clean_domain) or {}


def revoke_web_domain_permission(user_id: str, domain: str) -> bool:
    clean_domain = _normalize_web_domain(domain)
    with get_connection() as conn:
        revoked = conn.execute(
            """UPDATE web_domain_permissions
               SET is_active = 0, revoked_at = CURRENT_TIMESTAMP
               WHERE user_id = ? AND domain = ? AND is_active = 1""",
            (user_id, clean_domain),
        ).rowcount
        conn.commit()
    return revoked > 0


def get_web_domain_permission(user_id: str, domain: str) -> Optional[dict]:
    clean_domain = _normalize_web_domain(domain)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM web_domain_permissions WHERE user_id = ? AND domain = ?",
            (user_id, clean_domain),
        ).fetchone()
    return _web_domain_permission_row(row) if row else None


def list_web_domain_permissions(user_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM web_domain_permissions
               WHERE user_id = ?
               ORDER BY granted_at DESC""",
            (user_id,),
        ).fetchall()
    return [_web_domain_permission_row(row) for row in rows]


def check_web_domain_permission(
    user_id: str,
    domain: str,
    requested_scopes: Optional[list[str]] = None,
) -> dict:
    permission = get_web_domain_permission(user_id, domain)
    if not permission or not permission["is_active"]:
        return {"authorized": False, "error": "web_domain_permission_required"}
    missing = sorted(set(requested_scopes or []) - set(permission["scopes"]))
    if missing:
        return {
            "authorized": False,
            "error": "web_domain_scope_not_granted",
            "missing_scopes": missing,
            "granted_scopes": permission["scopes"],
        }
    return {"authorized": True, "permission": permission}


def _web_domain_permission_row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "domain": row["domain"],
        "scopes": json.loads(row["scopes"]),
        "is_active": bool(row["is_active"]),
        "granted_at": row["granted_at"],
        "revoked_at": row["revoked_at"],
    }


def _normalize_web_domain(domain: str) -> str:
    clean = str(domain or "").strip().lower()
    clean = clean.removeprefix("http://").removeprefix("https://").split("/")[0]
    clean = clean.removeprefix("www.")
    return clean[:240]


def register_push_token(
    user_id: str,
    device_id: str,
    apns_token: str,
    platform: str = "ios",
    environment: str = "development",
) -> dict:
    clean_device_id = str(device_id).strip()[:160]
    clean_token = str(apns_token).strip()[:500]
    token_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"contextlayer:push-token:{user_id}:{clean_device_id}"))
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO push_tokens
               (id, user_id, device_id, apns_token, platform, environment, is_active, revoked_at)
               VALUES (?, ?, ?, ?, ?, ?, 1, NULL)
               ON CONFLICT(user_id, device_id) DO UPDATE SET
                 apns_token = excluded.apns_token,
                 platform = excluded.platform,
                 environment = excluded.environment,
                 is_active = 1,
                 revoked_at = NULL,
                 registered_at = CURRENT_TIMESTAMP""",
            (
                token_id,
                user_id,
                clean_device_id,
                clean_token,
                platform[:40],
                environment[:40],
            ),
        )
        conn.commit()
    return get_push_token(user_id, clean_device_id) or {}


def get_push_token(user_id: str, device_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM push_tokens WHERE user_id = ? AND device_id = ?",
            (user_id, device_id),
        ).fetchone()
    return _push_token_row(row) if row else None


def list_push_tokens(user_id: str, active_only: bool = True) -> list[dict]:
    query = "SELECT * FROM push_tokens WHERE user_id = ?"
    params: list[object] = [user_id]
    if active_only:
        query += " AND is_active = 1"
    query += " ORDER BY registered_at DESC"
    with get_connection() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    return [_push_token_row(row) for row in rows]


def revoke_push_token(user_id: str, device_id: str) -> bool:
    with get_connection() as conn:
        revoked = conn.execute(
            """UPDATE push_tokens
               SET is_active = 0, revoked_at = CURRENT_TIMESTAMP
               WHERE user_id = ? AND device_id = ? AND is_active = 1""",
            (user_id, device_id),
        ).rowcount
        conn.commit()
    return revoked > 0


def queue_notification_routes(
    user_id: str,
    notification_type: str,
    deliver_after: int,
    payload_kind: str = "silent_local_insight",
) -> dict:
    tokens = list_push_tokens(user_id=user_id, active_only=True)
    queued = []
    now_ms = int(datetime.now().timestamp() * 1000)
    with get_connection() as conn:
        for token in tokens:
            route_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO notification_routes
                   (id, user_id, device_id, push_token_id, notification_type,
                    deliver_after, payload_kind, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', ?)""",
                (
                    route_id,
                    user_id,
                    token["device_id"],
                    token["id"],
                    notification_type[:80],
                    int(deliver_after),
                    payload_kind[:80],
                    now_ms,
                ),
            )
            queued.append({
                "id": route_id,
                "user_id": user_id,
                "device_id": token["device_id"],
                "push_token_id": token["id"],
                "notification_type": notification_type,
                "deliver_after": int(deliver_after),
                "payload_kind": payload_kind,
                "status": "queued",
                "created_at": now_ms,
            })
        conn.commit()
    return {"queued": len(queued), "routes": queued}


def list_notification_routes(user_id: str, limit: int = 100) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM notification_routes
               WHERE user_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (user_id, max(1, min(int(limit), 500))),
        ).fetchall()
    return [dict(row) for row in rows]


def _push_token_row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "device_id": row["device_id"],
        "apns_token": row["apns_token"],
        "token_prefix": str(row["apns_token"])[:12],
        "platform": row["platform"],
        "environment": row["environment"],
        "is_active": bool(row["is_active"]),
        "registered_at": row["registered_at"],
        "revoked_at": row["revoked_at"],
    }


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
