import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

@pytest.fixture(autouse=True)
def use_test_db(monkeypatch, tmp_path):
    # tmp_path is unique per test — no shared state, no Windows lock issues
    import database
    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'test.db')
    database.create_tables()

def test_create_tables_is_idempotent():
    from database import create_tables
    create_tables()
    create_tables()

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
    import datetime
    old_ts = int((datetime.datetime.now() - datetime.timedelta(days=10)).timestamp() * 1000)
    insert_event("https://old.com", "Old", "old.com", 10, None, old_ts)
    events = get_events_last_n_days(7)
    assert len(events) == 0

def test_save_and_get_persona():
    from database import save_persona, get_latest_persona
    persona = {"identity": {"role": "developer"}, "meta": {"event_count": 42}}
    save_persona(persona)
    result = get_latest_persona()
    assert result['identity']['role'] == 'developer'


def test_activity_summary_counts_recent_data():
    from database import (
        get_activity_summary,
        insert_context_access_log,
        insert_event,
        insert_feed_item,
        insert_persona_signal,
        save_context_contract,
    )
    import time

    now_ms = int(time.time() * 1000)
    insert_event("https://github.com", "GitHub", "github.com", 60, None, now_ms)
    insert_feed_item("youtube", "watch", "MCP tutorial", "", "", now_ms)
    insert_persona_signal("browser", "interest", "ai_agents", 1.0, 0.8, "MCP", now_ms)
    save_context_contract({
        "contract_id": "contract-1",
        "platform_type": "email",
        "facilities": ["reply_drafting"],
        "purpose": "draft replies",
        "retention": "session_only",
        "granted_context": ["communication_style"],
        "denied_context": [],
    })
    insert_context_access_log("contract-1", "email", "scoped_persona_returned", ["communication_style"])

    summary = get_activity_summary(days=7)

    assert summary["events"] == 1
    assert summary["feed_items"] == 1
    assert summary["persona_signals"] == 1
    assert summary["shareable_signals"] == 1
    assert summary["active_contracts"] == 1
    assert summary["access_logs"] == 1


def test_pcl_app_registration_and_query_logs():
    from database import (
        get_pcl_app,
        insert_pcl_query_log,
        list_pcl_apps,
        list_pcl_query_logs,
        register_pcl_app,
        revoke_pcl_app,
    )

    app = register_pcl_app(
        app_id="mail_app",
        name="Mail App",
        allowed_layers=["identity_role", "active_context"],
    )
    assert app["status"] == "active"
    assert get_pcl_app("mail_app")["allowed_layers"] == ["identity_role", "active_context"]
    assert list_pcl_apps()[0]["app_id"] == "mail_app"

    log = insert_pcl_query_log(
        app_id="mail_app",
        user_id="user_1",
        purpose="ui_personalization",
        requested_layers=["identity_role"],
        returned_layers=["identity_role"],
        feature_ids=["smart_reply"],
        status="returned",
    )
    logs = list_pcl_query_logs(app_id="mail_app")
    assert logs[0]["id"] == log["id"]
    assert logs[0]["feature_ids"] == ["smart_reply"]

    assert revoke_pcl_app("mail_app") is True
    assert get_pcl_app("mail_app")["status"] == "revoked"


def test_pcl_onboarding_seed_roundtrip():
    from database import get_pcl_onboarding_seed, save_pcl_onboarding_seed

    saved = save_pcl_onboarding_seed(
        user_id="user_1",
        answers={"identity": "founder"},
        profile_seed={"identity": {"role": "founder"}},
    )

    assert saved["user_id"] == "user_1"
    assert get_pcl_onboarding_seed("user_1")["profile_seed"]["identity"]["role"] == "founder"


def test_pcl_feature_event_usage_aggregation():
    from database import get_pcl_feature_usage, insert_pcl_feature_event
    import time

    now_ms = int(time.time() * 1000)
    insert_pcl_feature_event(
        app_id="mail_app",
        user_id="user_1",
        feature_id="smart_reply",
        feature_name="Smart Reply",
        event_type="used",
        weight=1.0,
        metadata={},
        timestamp=now_ms,
    )
    insert_pcl_feature_event(
        app_id="mail_app",
        user_id="user_1",
        feature_id="smart_reply",
        feature_name="Smart Reply",
        event_type="used",
        weight=2.0,
        metadata={},
        timestamp=now_ms,
    )

    usage = get_pcl_feature_usage("user_1")

    assert usage[0]["feature_id"] == "smart_reply"
    assert usage[0]["use_count"] == 2
    assert usage[0]["total_weight"] == 3.0


def test_pcl_integration_lifecycle():
    from database import (
        connect_pcl_integration,
        disconnect_pcl_integration,
        get_pcl_integration,
        list_pcl_integrations,
        update_pcl_integration_sync,
    )

    connected = connect_pcl_integration(
        source="gmail",
        name="Gmail",
        scopes=["email_metadata"],
        metadata={"account": "user"},
    )
    assert connected["status"] == "connected"
    assert get_pcl_integration("gmail")["scopes"] == ["email_metadata"]
    assert list_pcl_integrations()[0]["source"] == "gmail"

    synced = update_pcl_integration_sync("gmail", "stubbed", 0, "not implemented")
    assert synced["last_sync_status"] == "stubbed"
    assert synced["error"] == "not implemented"

    assert disconnect_pcl_integration("gmail") is True
    assert get_pcl_integration("gmail")["status"] == "disconnected"


def test_pcl_delete_user_app_integration_and_query_data():
    from database import (
        clear_pcl_query_logs,
        connect_pcl_integration,
        delete_pcl_app_data,
        delete_pcl_integration_data,
        delete_pcl_user_data,
        get_pcl_app,
        get_pcl_feature_usage,
        get_pcl_integration,
        get_pcl_onboarding_seed,
        insert_feed_item,
        insert_pcl_feature_event,
        insert_pcl_query_log,
        insert_persona_signal,
        list_pcl_query_logs,
        register_pcl_app,
        save_pcl_onboarding_seed,
    )
    import time

    now_ms = int(time.time() * 1000)
    register_pcl_app("delete_app", "Delete App", ["identity_role"])
    save_pcl_onboarding_seed("delete_user", {"identity": "builder"}, {"identity": {"role": "builder"}})
    insert_pcl_feature_event("delete_app", "delete_user", "compose", "Compose", "used", 1.0, {}, now_ms)
    insert_pcl_query_log(
        "delete_app",
        "delete_user",
        "ui_personalization",
        ["identity_role"],
        ["identity_role"],
        ["compose"],
        "returned",
    )

    user_deleted = delete_pcl_user_data("delete_user")

    assert user_deleted["onboarding_seeds"] == 1
    assert user_deleted["feature_events"] == 1
    assert user_deleted["query_logs"] == 1
    assert get_pcl_onboarding_seed("delete_user") is None
    assert get_pcl_feature_usage("delete_user") == []
    assert list_pcl_query_logs(app_id="delete_app") == []

    insert_pcl_feature_event("delete_app", "other_user", "compose", "Compose", "used", 1.0, {}, now_ms)
    insert_pcl_query_log(
        "delete_app",
        "other_user",
        "ui_personalization",
        ["identity_role"],
        ["identity_role"],
        ["compose"],
        "returned",
    )

    app_deleted = delete_pcl_app_data("delete_app")

    assert app_deleted["apps"] == 1
    assert app_deleted["feature_events"] == 1
    assert app_deleted["query_logs"] == 1
    assert get_pcl_app("delete_app") is None

    insert_pcl_query_log("another_app", "other_user", "", [], [], [], "denied")
    assert clear_pcl_query_logs(user_id="other_user") == 1

    connect_pcl_integration("gmail", "Gmail", ["email_metadata"], {})
    insert_feed_item("gmail", "email_metadata", "subject only", "sender", "", now_ms)
    insert_persona_signal("gmail", "behavior", "async_communication", 1.0, 0.8, "", now_ms)

    integration_deleted = delete_pcl_integration_data("gmail")

    assert integration_deleted["integrations"] == 1
    assert integration_deleted["feed_items"] == 1
    assert integration_deleted["persona_signals"] == 1
    assert get_pcl_integration("gmail") is None
