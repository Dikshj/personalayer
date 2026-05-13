import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "sdk" / "python"))

from personal_context_layer import PersonalContextLayer


class FakeResponse:
    def __init__(self, payload=None):
        self.payload = payload or {"status": "ok"}

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_python_sdk_posts_core_requests(monkeypatch):
    calls = []

    def fake_post(url, json, headers=None, timeout=10):
        calls.append({"method": "POST", "url": url, "json": json, "headers": headers, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr("personal_context_layer.httpx.post", fake_post)
    pcl = PersonalContextLayer(app_id="mail_app", api_key="cl_test_key", user_token="user:user_1")

    pcl.register_app("Mail App", ["identity_role"])
    pcl.track_feature("user_1", "smart_reply", "Smart Reply")
    pcl.track("Smart Reply", user_id="user_1", session_id="s1", timestamp=123, metadata={"hour_of_day": 9})
    pcl.generate_cold_start(user_id="user_1", app_name="Mail App", features=["Smart Reply"], role="founder")
    pcl.personalize("user_1", [{"feature_id": "smart_reply", "name": "Smart Reply"}])
    pcl.get_context_bundle(user_id="user_1", intent="adapt_ui")
    pcl.heartbeat(user_id="user_1", project="ContextLayer", session_depth="deep-work")
    pcl.feedback("bundle_1", "accepted", ["Smart Reply"], user_id="user_1")
    pcl.revoke_app()

    assert calls[0]["url"] == "http://127.0.0.1:7823/pcl/apps"
    assert calls[0]["json"]["allowed_layers"] == ["identity_role"]
    assert calls[1]["url"] == "http://127.0.0.1:7823/pcl/events/feature"
    assert calls[1]["json"]["feature_id"] == "smart_reply"
    assert calls[2]["url"] == "http://127.0.0.1:7823/v1/ingest/sdk"
    assert calls[2]["json"]["feature_id"] == "smart-reply"
    assert calls[2]["json"]["session_id"] == "s1"
    assert calls[2]["json"]["metadata"] == {"hour_of_day": 9}
    assert calls[3]["url"] == "http://127.0.0.1:7823/v1/context/cold-start"
    assert calls[3]["json"]["features"] == ["Smart Reply"]
    assert calls[4]["url"] == "http://127.0.0.1:7823/pcl/query"
    assert calls[4]["json"]["features"] == [{"feature_id": "smart_reply", "name": "Smart Reply"}]
    assert calls[5]["url"] == "http://127.0.0.1:7823/v1/context/bundle"
    assert calls[5]["json"]["intent"] == "adapt_ui"
    assert calls[5]["headers"] == {
        "Authorization": "Bearer cl_test_key",
        "x-user-token": "user:user_1",
    }
    assert calls[6]["url"] == "http://127.0.0.1:7823/v1/context/heartbeat"
    assert calls[6]["json"]["active_apps"] == ["mail_app"]
    assert calls[7]["url"] == "http://127.0.0.1:7823/v1/context/feedback"
    assert calls[7]["json"]["features_actually_used"] == ["smart-reply"]
    assert calls[8]["url"] == "http://127.0.0.1:7823/pcl/apps/mail_app/revoke"


def test_python_sdk_delete_requests(monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=10):
        calls.append({"method": "GET", "url": url, "params": params, "headers": headers, "timeout": timeout})
        return FakeResponse()

    def fake_delete(url, params=None, headers=None, timeout=10):
        calls.append({"method": "DELETE", "url": url, "params": params, "headers": headers, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr("personal_context_layer.httpx.get", fake_get)
    monkeypatch.setattr("personal_context_layer.httpx.delete", fake_delete)
    pcl = PersonalContextLayer(app_id="mail_app")

    pcl.delete_app_data()
    pcl.clear_query_log(user_id="user_1")
    pcl.activity(user_id="user_1", limit=10)
    pcl.delete_user_data("user_1")
    pcl.delete_all_context(user_id="user_1")

    assert calls[0] == {
        "method": "DELETE",
        "url": "http://127.0.0.1:7823/pcl/apps/mail_app/data",
        "params": None,
        "headers": {},
        "timeout": 10,
    }
    assert calls[1] == {
        "method": "DELETE",
        "url": "http://127.0.0.1:7823/pcl/query-log",
        "params": {"app_id": "mail_app", "user_id": "user_1"},
        "headers": {},
        "timeout": 10,
    }
    assert calls[2] == {
        "method": "GET",
        "url": "http://127.0.0.1:7823/v1/context/activity",
        "params": {"user_id": "user_1", "limit": 10},
        "headers": {},
        "timeout": 10,
    }
    assert calls[3] == {
        "method": "DELETE",
        "url": "http://127.0.0.1:7823/pcl/users/user_1/data",
        "params": None,
        "headers": {},
        "timeout": 10,
    }
    assert calls[4] == {
        "method": "DELETE",
        "url": "http://127.0.0.1:7823/v1/context/all",
        "params": {"user_id": "user_1"},
        "headers": {},
        "timeout": 10,
    }
