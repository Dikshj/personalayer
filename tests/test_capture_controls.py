"""Capture controls: Agent Reach channels, device permission reports, and
one-time daemon enrollment codes — all owned per-user."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

USER_A = "supabase:aaaa"
USER_B = "supabase:bbbb"


def _db(monkeypatch, tmp_path, name):
    import database
    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / name)
    database.create_tables()
    return database


def test_agent_reach_channels_are_per_user(monkeypatch, tmp_path):
    db = _db(monkeypatch, tmp_path, 'reach.db')

    # Default: catalog present, all disabled.
    channels = db.list_agent_reach_channels(USER_A)
    assert len(channels) == len(db.AGENT_REACH_CHANNEL_CATALOG)
    assert all(c["enabled"] is False for c in channels)

    db.set_agent_reach_channel(USER_A, "email", True)
    a = {c["channel"]: c["enabled"] for c in db.list_agent_reach_channels(USER_A)}
    b = {c["channel"]: c["enabled"] for c in db.list_agent_reach_channels(USER_B)}
    assert a["email"] is True
    assert b["email"] is False  # isolation

    # Unknown channel rejected.
    assert db.set_agent_reach_channel(USER_A, "carrier_pigeon", True).get("error") == "unknown_channel"

    # Toggle back off.
    db.set_agent_reach_channel(USER_A, "email", False)
    assert {c["channel"]: c["enabled"] for c in db.list_agent_reach_channels(USER_A)}["email"] is False


def test_device_permissions_report_and_isolation(monkeypatch, tmp_path):
    db = _db(monkeypatch, tmp_path, 'perms.db')

    db.report_device_permissions(USER_A, "iphone-1", {"healthkit": "granted", "contacts": "denied"})
    a = db.list_device_permissions(USER_A)
    assert {p["permission"]: p["state"] for p in a} == {"healthkit": "granted", "contacts": "denied"}
    assert db.list_device_permissions(USER_B) == []  # isolation

    # Upsert updates state in place.
    db.report_device_permissions(USER_A, "iphone-1", {"healthkit": "denied"})
    a = {p["permission"]: p["state"] for p in db.list_device_permissions(USER_A)}
    assert a["healthkit"] == "denied"


def test_enroll_token_is_one_time_and_expires(monkeypatch, tmp_path):
    db = _db(monkeypatch, tmp_path, 'enroll.db')

    issued = db.create_capture_enroll_token(USER_A, ttl_seconds=600)
    assert issued["code"] and issued["user_id"] == USER_A

    # Redeems once, returns the owner.
    assert db.redeem_capture_enroll_token(issued["code"]) == USER_A
    # Second redeem fails (consumed).
    assert db.redeem_capture_enroll_token(issued["code"]) is None
    # Unknown code fails.
    assert db.redeem_capture_enroll_token("NOPE0000") is None

    # Expired code fails.
    expired = db.create_capture_enroll_token(USER_B, ttl_seconds=-10)
    assert db.redeem_capture_enroll_token(expired["code"]) is None
