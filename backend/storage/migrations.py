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


def _migration_004_integration_sync_cursors(conn: sqlite3.Connection) -> None:
    ensure_column(conn, "pcl_integrations", "sync_cursor", "TEXT DEFAULT '{}'")
    ensure_column(conn, "pcl_integrations", "next_sync_after", "INTEGER")


def _migration_005_integration_account_state(conn: sqlite3.Connection) -> None:
    ensure_column(conn, "pcl_integrations", "account_hint", "TEXT DEFAULT ''")
    ensure_column(conn, "pcl_integrations", "auth_status", "TEXT DEFAULT 'local_metadata'")
    ensure_column(conn, "pcl_integrations", "auth_expires_at", "INTEGER")


def _migration_006_integration_oauth_states(conn: sqlite3.Connection) -> None:
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


def _migration_007_local_knowledge_graph(conn: sqlite3.Connection) -> None:
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


def _migration_008_web_domain_permissions(conn: sqlite3.Connection) -> None:
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


def _migration_009_device_push_routing(conn: sqlite3.Connection) -> None:
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


def _migration_010_integration_oauth_tokens(conn: sqlite3.Connection) -> None:
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


def _migration_011_raw_event_vault_payload(conn: sqlite3.Connection) -> None:
    ensure_column(conn, "raw_events", "raw_payload", "TEXT DEFAULT '{}'")


def _migration_012_integration_user_scope(conn: sqlite3.Connection) -> None:
    """Give pcl_integrations per-user ownership.

    Old rows were keyed by ``source`` alone (global). Rebuild the table with a
    composite ``(user_id, source)`` primary key so one customer can never see
    or change another's connector state. Existing rows are attributed to their
    metadata.user_id when present (OAuth connections recorded it), otherwise to
    'local_user' for backward compatibility. SQLite can't drop the old primary
    key in place, so this is the standard table-copy migration.
    """
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(pcl_integrations)").fetchall()}
    if not columns:
        # Fresh database: create_tables() already builds the user-scoped shape.
        return
    if "user_id" in columns:
        # Already migrated.
        return
    conn.execute("""
        CREATE TABLE pcl_integrations_new (
            user_id TEXT NOT NULL DEFAULT 'local_user',
            source TEXT NOT NULL,
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
            disconnected_at DATETIME,
            PRIMARY KEY (user_id, source)
        )
    """)
    conn.execute("""
        INSERT OR REPLACE INTO pcl_integrations_new (
            user_id, source, name, status, scopes, metadata, last_sync_at,
            last_sync_status, items_synced, sync_cursor, next_sync_after,
            account_hint, auth_status, auth_expires_at, error, connected_at, disconnected_at
        )
        SELECT
            COALESCE(NULLIF(json_extract(metadata, '$.user_id'), ''), 'local_user'),
            source, name, status, scopes, metadata, last_sync_at,
            last_sync_status, items_synced, sync_cursor, next_sync_after,
            account_hint, auth_status, auth_expires_at, error, connected_at, disconnected_at
        FROM pcl_integrations
    """)
    conn.execute("DROP TABLE pcl_integrations")
    conn.execute("ALTER TABLE pcl_integrations_new RENAME TO pcl_integrations")


def _migration_013_capture_controls(conn: sqlite3.Connection) -> None:
    """Per-user tables for capture controls: Agent Reach channels, native device
    permission reports, and one-time daemon enrollment codes."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_reach_channels (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            channel TEXT NOT NULL,
            enabled INTEGER DEFAULT 0,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, channel)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS device_permissions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            device_id TEXT NOT NULL,
            permission TEXT NOT NULL,
            state TEXT DEFAULT 'undetermined',
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, device_id, permission)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS capture_enroll_tokens (
            code TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at INTEGER NOT NULL,
            consumed_at DATETIME
        )
    """)


def _migration_014_persona_signal_user_scope(conn: sqlite3.Connection) -> None:
    """Assign every persona signal to one user.

    Historical signals predate account ownership and are retained under
    ``local_user``. Authenticated accounts rebuild their onboarding signals
    from their user-scoped onboarding seed when the dashboard is opened.
    """
    ensure_column(conn, "persona_signals", "user_id", "TEXT NOT NULL DEFAULT 'local_user'")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_persona_signals_user_time "
        "ON persona_signals(user_id, timestamp DESC)"
    )


MIGRATIONS: tuple[tuple[str, Migration], ...] = (
    ("001_context_contract_status", _migration_001_context_contract_status),
    ("002_persona_feedback_calibration", _migration_002_persona_feedback_calibration),
    ("003_contextlayer_refresh_columns", _migration_003_contextlayer_refresh_columns),
    ("004_integration_sync_cursors", _migration_004_integration_sync_cursors),
    ("005_integration_account_state", _migration_005_integration_account_state),
    ("006_integration_oauth_states", _migration_006_integration_oauth_states),
    ("007_local_knowledge_graph", _migration_007_local_knowledge_graph),
    ("008_web_domain_permissions", _migration_008_web_domain_permissions),
    ("009_device_push_routing", _migration_009_device_push_routing),
    ("010_integration_oauth_tokens", _migration_010_integration_oauth_tokens),
    ("011_raw_event_vault_payload", _migration_011_raw_event_vault_payload),
    ("012_integration_user_scope", _migration_012_integration_user_scope),
    ("013_capture_controls", _migration_013_capture_controls),
    ("014_persona_signal_user_scope", _migration_014_persona_signal_user_scope),
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
