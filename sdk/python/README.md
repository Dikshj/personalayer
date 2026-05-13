# Personal Context Layer Python SDK

Minimal local SDK stub for the prototype daemon.

```python
from personal_context_layer import PersonalContextLayer

pcl = PersonalContextLayer(
    app_id="mail_app",
    api_key="cl_test_...",      # optional for local mode, required for developer auth
    user_token="user:user_1",   # local prototype user token shape
)

pcl.register_app(
    name="Mail App",
    allowed_layers=["identity_role", "capability_signals", "active_context"],
)

pcl.track_feature(
    user_id="user_1",
    feature_id="smart_reply",
    feature_name="Smart Reply",
)

pcl.track(
    user_id="user_1",
    feature_id="smart_reply",
    action="used",
    session_id="session_1",
    metadata={"hour_of_day": 9, "day_of_week": 1, "subject_category": "email"},
)

pcl.generate_cold_start(
    user_id="user_1",
    app_name="Mail App",
    features=["smart_reply", "newsletter_filter"],
    role="founder",
    domain="developer tools",
)

pcl.heartbeat(
    user_id="user_1",
    project="Inbox cleanup",
    active_apps=["mail_app"],
    inferred_intent="adapt_ui",
    session_depth="moderate",
)

bundle = pcl.personalize(
    user_id="user_1",
    features=[
        {"feature_id": "smart_reply", "name": "Smart Reply"},
        {"feature_id": "newsletter_filter", "name": "Newsletter Filter"},
    ],
)

context = pcl.get_context_bundle(user_id="user_1", intent="adapt_ui")
pcl.feedback(
    bundle_id=context["bundle_id"],
    outcome="accepted",
    features_actually_used=["smart_reply"],
    user_id="user_1",
)

pcl.activity(user_id="user_1")
pcl.clear_query_log(user_id="user_1")
pcl.revoke_app()
pcl.delete_app_data()
pcl.delete_user_data("user_1")
pcl.delete_all_context(user_id="user_1")
```

`track_feature` and `personalize` keep compatibility with the older local prototype routes. New integrations should prefer `track`, `generate_cold_start`, `heartbeat`, `get_context_bundle`, and `feedback`, which use the `/v1` ContextLayer API. `track` accepts only whitelisted metadata: `hour_of_day`, `day_of_week`, and `subject_category`.

Apps should query at runtime and avoid storing the returned bundle. The daemon logs each query for the user-visible activity trail.

When `api_key` is set, the SDK sends `Authorization: Bearer {api_key}`. When `user_token` is set, it sends `x-user-token`. Authenticated bundle requests require an active user consent record for the app and all requested scopes.

Use `revoke_app` when the user disconnects an app. Use `delete_app_data` or `delete_user_data` when the user asks for stored records to be removed instead of only stopping future access.
