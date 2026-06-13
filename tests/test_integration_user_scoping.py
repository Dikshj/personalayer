"""Proves pcl_integrations is owned per-user: one customer can never see,
modify, sync, disconnect, or delete another customer's connector state.
Also covers Supabase JWT verification and the backward-compatible migration."""
import base64
import hashlib
import hmac
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

USER_A = "supabase:aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
USER_B = "supabase:bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def _fresh_db(monkeypatch, tmp_path, name):
    import database
    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / name)
    database.create_tables()
    return database


def test_integrations_are_isolated_per_user(monkeypatch, tmp_path):
    db = _fresh_db(monkeypatch, tmp_path, 'scope.db')

    db.connect_pcl_integration(source="github", name="GitHub", scopes=["public_activity"],
                               metadata={"username": "alice"}, user_id=USER_A)
    db.connect_pcl_integration(source="github", name="GitHub", scopes=["public_activity"],
                               metadata={"username": "bob"}, user_id=USER_B)
    db.connect_pcl_integration(source="notion", name="Notion", scopes=["page_metadata"],
                               metadata={}, user_id=USER_A)

    # Listing is scoped: A sees github+notion, B sees only github.
    a_sources = {i["source"] for i in db.list_pcl_integrations(USER_A)}
    b_sources = {i["source"] for i in db.list_pcl_integrations(USER_B)}
    assert a_sources == {"github", "notion"}
    assert b_sources == {"github"}

    # Reads are scoped and don't bleed across users.
    assert db.get_pcl_integration("github", user_id=USER_A)["metadata"]["username"] == "alice"
    assert db.get_pcl_integration("github", user_id=USER_B)["metadata"]["username"] == "bob"
    assert db.get_pcl_integration("notion", user_id=USER_B) is None

    # Disconnect by A must not touch B.
    assert db.disconnect_pcl_integration("github", user_id=USER_A) is True
    assert db.get_pcl_integration("github", user_id=USER_A)["status"] == "disconnected"
    assert db.get_pcl_integration("github", user_id=USER_B)["status"] == "connected"

    # Sync-state writes by A must not touch B.
    db.update_pcl_integration_sync(source="github", status="ok", items_synced=5, user_id=USER_A)
    assert db.get_pcl_integration("github", user_id=USER_A)["items_synced"] == 5
    assert db.get_pcl_integration("github", user_id=USER_B)["items_synced"] == 0

    # Delete by A must not touch B's row.
    db.delete_pcl_integration_data("github", user_id=USER_A)
    assert db.get_pcl_integration("github", user_id=USER_A) is None
    assert db.get_pcl_integration("github", user_id=USER_B)["metadata"]["username"] == "bob"


def test_sync_integration_runs_per_user(monkeypatch, tmp_path):
    db = _fresh_db(monkeypatch, tmp_path, 'scope_sync.db')
    import collectors.github
    monkeypatch.setattr(collectors.github, "collect_github", lambda username: 3)

    db.connect_pcl_integration(source="github", name="GitHub", scopes=["public_activity"],
                               metadata={"username": "alice"}, user_id=USER_A)

    from pcl.integration_jobs import sync_integration
    # User B has no github connection — their sync must not see A's.
    assert sync_integration("github", user_id=USER_B)["status"] == "error"
    # User A syncs their own connection.
    assert sync_integration("github", user_id=USER_A)["status"] == "ok"
    assert db.get_pcl_integration("github", user_id=USER_A)["items_synced"] == 3
    assert db.get_pcl_integration("github", user_id=USER_B) is None


def _make_jwt(secret: str, claims: dict) -> str:
    def seg(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()
    header = seg({"alg": "HS256", "typ": "JWT"})
    payload = seg(claims)
    sig = hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    return f"{header}.{payload}.{base64.urlsafe_b64encode(sig).rstrip(b'=').decode()}"


def test_supabase_jwt_verification(monkeypatch):
    from pcl import auth
    secret = "test-jwt-secret"
    monkeypatch.setenv("SUPABASE_JWT_SECRET", secret)

    token = _make_jwt(secret, {"sub": "user-123", "email": "a@example.com", "exp": int(time.time()) + 3600})
    session = auth.verify_supabase_jwt(token)
    assert session and session["user_id"] == "supabase:user-123"

    # Tampered signature is rejected.
    assert auth.verify_supabase_jwt(token[:-3] + "zzz") is None
    # Wrong secret is rejected.
    assert auth.verify_supabase_jwt(_make_jwt("other-secret", {"sub": "x", "exp": int(time.time()) + 60})) is None
    # Expired token is rejected.
    assert auth.verify_supabase_jwt(_make_jwt(secret, {"sub": "x", "exp": int(time.time()) - 10})) is None
    # No secret configured -> no verification.
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    assert auth.verify_supabase_jwt(token) is None


def test_migration_backfills_user_id_from_metadata(monkeypatch, tmp_path):
    from storage.migrations import _migration_012_integration_user_scope
    conn = sqlite3.connect(tmp_path / "legacy.db")
    conn.row_factory = sqlite3.Row
    # Recreate the OLD global schema (source as sole primary key).
    conn.execute("""
        CREATE TABLE pcl_integrations (
            source TEXT PRIMARY KEY, name TEXT NOT NULL, status TEXT DEFAULT 'connected',
            scopes TEXT DEFAULT '[]', metadata TEXT DEFAULT '{}', last_sync_at DATETIME,
            last_sync_status TEXT DEFAULT '', items_synced INTEGER DEFAULT 0,
            sync_cursor TEXT DEFAULT '{}', next_sync_after INTEGER, account_hint TEXT DEFAULT '',
            auth_status TEXT DEFAULT 'local_metadata', auth_expires_at INTEGER, error TEXT DEFAULT '',
            connected_at DATETIME DEFAULT CURRENT_TIMESTAMP, disconnected_at DATETIME
        )
    """)
    conn.execute("INSERT INTO pcl_integrations (source, name, metadata) VALUES (?, ?, ?)",
                 ("gmail", "Gmail", json.dumps({"user_id": USER_A})))
    conn.execute("INSERT INTO pcl_integrations (source, name, metadata) VALUES (?, ?, ?)",
                 ("github", "GitHub", "{}"))
    conn.commit()

    _migration_012_integration_user_scope(conn)

    cols = {r["name"] for r in conn.execute("PRAGMA table_info(pcl_integrations)").fetchall()}
    assert "user_id" in cols
    rows = {r["source"]: r["user_id"] for r in conn.execute("SELECT source, user_id FROM pcl_integrations").fetchall()}
    assert rows["gmail"] == USER_A          # backfilled from metadata.user_id
    assert rows["github"] == "local_user"   # default for rows without metadata user
    conn.close()
