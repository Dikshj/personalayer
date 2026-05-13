# backend/interfaces/http_api.py
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from core.daemon import daemon
from core.events import BrowserActivityEvent, FeedActivityEvent
from database import (
    add_to_waitlist,
    clear_pcl_query_logs,
    connect_pcl_integration,
    create_tables,
    delete_pcl_app_data,
    delete_pcl_integration_data,
    delete_pcl_user_data,
    disconnect_pcl_integration,
    get_activity_summary,
    grant_app_consent,
    get_user_profile_record,
    list_app_permissions,
    list_daily_refresh_jobs,
    list_feature_signals,
    list_privacy_filter_drops,
    list_developer_api_keys,
    get_context_access_logs,
    get_pcl_app,
    get_pcl_feature_usage,
    get_pcl_onboarding_seed,
    get_waitlist_count,
    insert_persona_feedback,
    insert_pcl_query_log,
    insert_pcl_feature_event,
    list_context_contracts,
    list_pcl_apps,
    list_pcl_integrations,
    list_pcl_query_logs,
    create_developer_api_key,
    delete_old_raw_context_events,
    register_pcl_app,
    register_developer_app,
    revoke_pcl_app,
    revoke_context_contract,
    revoke_app_consent,
    save_pcl_onboarding_seed,
    upsert_developer,
    update_pcl_integration_sync,
)
from living_persona import build_living_persona
from policy import build_scoped_persona, negotiate_context_contract
from pcl.composer import compose_decision_bundle
from pcl.models import (
    ActiveContext,
    AppFeature,
    ContextLayer,
    ContextQuery,
)
from pcl.permissions import resolve_allowed_layers
from pcl.onboarding import ONBOARDING_QUESTIONS, build_onboarding_seed
from pcl.profile import build_local_user_context_profile
from pcl.privacy import strip_raw_content
from pcl.integrations import default_integration, integration_catalog
from pcl.integration_jobs import sync_integration
from pcl.contextlayer import (
    apply_context_feedback,
    authorize_developer_context_request,
    build_context_bundle,
    get_contextlayer_activity,
    hard_delete_contextlayer_user,
    ingest_context_event,
    run_decay_engine,
    run_inductive_memory_job,
    run_profile_synthesizer,
    run_reflective_memory_job,
    update_active_context,
)
from pcl.assistant import personal_assistant_chat
from pcl.cold_start import generate_cold_start_signals
from pcl.daily_refresh import run_daily_refresh, run_due_daily_refreshes
from pcl.proxy import proxy_chat_completion
from predictions import predict_next_context
from scheduler import create_scheduler, start_background_collectors


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    scheduler = create_scheduler()
    scheduler.start()
    start_background_collectors()
    yield
    scheduler.shutdown()


app = FastAPI(title="PersonaLayer", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["chrome-extension://*", "http://localhost:*"],
    allow_methods=["POST", "GET", "DELETE"],
    allow_headers=["Content-Type"],
)

PROJECT_ROOT = Path(__file__).parent.parent.parent
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
if DASHBOARD_DIR.exists():
    app.mount("/dashboard", StaticFiles(directory=str(DASHBOARD_DIR), html=True), name="dashboard")

LANDING_DIR = PROJECT_ROOT / "landing"
if LANDING_DIR.exists():
    app.mount("/landing", StaticFiles(directory=str(LANDING_DIR), html=True), name="landing")


class WaitlistEntry(BaseModel):
    email: str
    source: Optional[str] = "landing"


@app.post("/waitlist")
async def join_waitlist(entry: WaitlistEntry):
    if "@" not in entry.email or "." not in entry.email:
        return {"status": "error", "error": "Invalid email"}
    added = add_to_waitlist(entry.email, entry.source or "landing")
    return {
        "status": "ok" if added else "already_joined",
        "count": get_waitlist_count(),
    }


@app.get("/waitlist/count")
async def waitlist_count():
    return {"count": get_waitlist_count()}


class BrowsingEvent(BaseModel):
    url: str
    title: Optional[str] = ""
    time_spent_seconds: Optional[int] = 0
    timestamp: int


@app.post("/event")
async def receive_event(event: BrowsingEvent):
    result = daemon.ingest_browser_activity(BrowserActivityEvent(
        url=event.url,
        title=event.title or "",
        time_spent_seconds=event.time_spent_seconds or 0,
        timestamp=event.timestamp,
    ))
    response = {"status": result.status}
    if result.reason:
        response["reason"] = result.reason
    return response


@app.get("/health")
async def health():
    return {"status": "ok", "service": "personalayer"}


@app.get("/daemon/status")
async def daemon_status():
    return daemon.status()


@app.get("/persona")
async def get_persona_endpoint():
    from database import get_latest_persona
    persona = get_latest_persona()
    if not persona:
        return {"error": "No persona yet. Browse for 24h or run: python persona.py"}
    return persona


@app.get("/persona/living")
async def get_living_persona_endpoint(days: int = 30):
    return build_living_persona(days=days)


@app.get("/activity/summary")
async def get_activity_summary_endpoint(days: int = 30):
    days = max(1, min(days, 365))
    return get_activity_summary(days=days)


@app.get("/predictions/next-context")
async def get_next_context_prediction(days: int = 14):
    return predict_next_context(days=days)


class PclQueryRequest(BaseModel):
    app_id: str
    user_id: str = "local_user"
    purpose: str = "ui_personalization"
    requested_layers: list[ContextLayer] = []
    features: list[AppFeature] = []


class PclAppRegistration(BaseModel):
    app_id: str
    name: str
    allowed_layers: list[ContextLayer]


class PclFeatureEventRequest(BaseModel):
    app_id: str
    user_id: str = "local_user"
    feature_id: str
    feature_name: str = ""
    event_type: str = "used"
    weight: float = 1.0
    metadata: dict = {}
    timestamp: int


class PclOnboardingSeedRequest(BaseModel):
    user_id: str = "local_user"
    answers: dict


class PclIntegrationConnectRequest(BaseModel):
    metadata: dict = {}


class ContextLayerEventRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    app_id: str
    feature_id: str
    action: str
    session_id: Optional[str] = ""
    timestamp: Optional[int] = None
    user_id: str = "local_user"
    is_synthetic: bool = False
    metadata: dict = {}


class ContextBundleRequest(BaseModel):
    user_id: str = "local_user"
    app_id: str
    intent: str = "full_profile"
    requested_scopes: list[str] = []


class ContextFeedbackRequest(BaseModel):
    user_id: str = "local_user"
    bundle_id: str
    app_id: str
    outcome: str
    features_actually_used: list[str] = []


class ContextHeartbeatRequest(BaseModel):
    user_id: str = "local_user"
    project: Optional[str] = ""
    active_apps: list[str] = []
    inferred_intent: Optional[str] = ""
    session_depth: str = "shallow"


class RawEventCleanupRequest(BaseModel):
    user_id: str = "local_user"
    older_than_days: int = 7


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[dict]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False
    user_id: Optional[str] = "local_user"
    app_id: Optional[str] = "human_api_proxy"


class AssistantChatRequest(BaseModel):
    message: str
    user_id: str = "local_user"
    model: str = "gpt-4.1-mini"


class DailyRefreshRequest(BaseModel):
    user_id: str = "local_user"
    timezone: str = "UTC"
    job_id: Optional[str] = None
    step_completed: int = 0


class DueDailyRefreshRequest(BaseModel):
    now: Optional[str] = None


class ColdStartRequest(BaseModel):
    user_id: str = "local_user"
    app_id: str
    app_name: Optional[str] = ""
    features: list[str] = []
    role: Optional[str] = ""
    domain: Optional[str] = ""
    skill_level: Optional[str] = "intermediate"


class ConsentRequest(BaseModel):
    user_id: str = "local_user"
    app_id: str
    developer_id: Optional[str] = ""
    scopes: list[str] = ["getFeatureUsage"]
    granted_via: str = "explicit"


class DeveloperRegistrationRequest(BaseModel):
    email: str
    name: Optional[str] = ""


class DeveloperAppRequest(BaseModel):
    developer_id: str
    app_id: str
    name: str
    domain: Optional[str] = ""


class DeveloperKeyRequest(BaseModel):
    developer_id: str
    app_id: Optional[str] = ""
    env: str = "test"


def _resolve_context_user_id(payload_user_id: str, user_token: str) -> str:
    token = (user_token or "").strip()
    if token.startswith("user:"):
        return token[5:] or payload_user_id
    return payload_user_id


@app.get("/pcl/onboarding/questions")
async def get_pcl_onboarding_questions():
    return {"questions": ONBOARDING_QUESTIONS}


@app.post("/pcl/onboarding/seed")
async def seed_pcl_onboarding(payload: PclOnboardingSeedRequest):
    profile_seed = build_onboarding_seed(payload.answers)
    saved = save_pcl_onboarding_seed(payload.user_id, payload.answers, profile_seed)
    return {
        "status": "ok",
        "user_id": payload.user_id,
        "profile_seed": saved["profile_seed"],
    }


@app.post("/pcl/apps")
async def register_personal_context_app(payload: PclAppRegistration):
    return register_pcl_app(
        app_id=payload.app_id,
        name=payload.name,
        allowed_layers=payload.allowed_layers,
    )


@app.get("/pcl/apps")
async def get_personal_context_apps(limit: int = 100):
    return {"apps": list_pcl_apps(limit=limit)}


@app.post("/pcl/apps/{app_id}/revoke")
async def revoke_personal_context_app(app_id: str):
    revoked = revoke_pcl_app(app_id)
    return {"status": "revoked" if revoked else "not_found_or_already_revoked"}


@app.delete("/pcl/apps/{app_id}/data")
async def delete_personal_context_app_data(app_id: str):
    deleted = delete_pcl_app_data(app_id)
    return {"status": "deleted" if deleted["apps"] else "not_found", "deleted": deleted}


@app.get("/pcl/query-log")
async def get_personal_context_query_log(app_id: Optional[str] = None, limit: int = 100):
    return {"logs": list_pcl_query_logs(app_id=app_id, limit=limit)}


@app.delete("/pcl/query-log")
async def delete_personal_context_query_log(
    app_id: Optional[str] = None,
    user_id: Optional[str] = None,
):
    return {
        "status": "deleted",
        "deleted": {"query_logs": clear_pcl_query_logs(app_id=app_id, user_id=user_id)},
    }


@app.get("/pcl/profile")
async def get_personal_context_profile(user_id: str = "local_user"):
    return build_local_user_context_profile(user_id).model_dump()


@app.delete("/pcl/users/{user_id}/data")
async def delete_personal_context_user_data(user_id: str):
    return {"status": "deleted", "deleted": delete_pcl_user_data(user_id)}


@app.get("/pcl/feature-usage")
async def get_personal_context_feature_usage(
    user_id: str = "local_user",
    app_id: Optional[str] = None,
    days: int = 90,
):
    days = max(1, min(days, 365))
    return {
        "user_id": user_id,
        "app_id": app_id,
        "features": get_pcl_feature_usage(user_id=user_id, app_id=app_id, days=days),
    }


@app.get("/pcl/onboarding/seed")
async def get_pcl_onboarding_seed_endpoint(user_id: str = "local_user"):
    seed = get_pcl_onboarding_seed(user_id)
    if not seed:
        return {"error": "not_found"}
    return seed


@app.get("/pcl/integrations/catalog")
async def get_pcl_integration_catalog():
    return {"integrations": integration_catalog()}


@app.get("/pcl/integrations")
async def get_pcl_integrations():
    connected = {item["source"]: item for item in list_pcl_integrations()}
    rows = []
    for catalog_item in integration_catalog():
        source = catalog_item["source"]
        rows.append({
            **catalog_item,
            **connected.get(source, {
                "status": "available",
                "metadata": {},
                "last_sync_at": None,
                "last_sync_status": "",
                "items_synced": 0,
                "error": "",
                "connected_at": None,
                "disconnected_at": None,
            }),
        })
    return {"integrations": rows}


@app.post("/pcl/integrations/{source}/connect")
async def connect_pcl_integration_endpoint(source: str, payload: PclIntegrationConnectRequest):
    try:
        config = default_integration(source)
    except ValueError:
        return {"status": "error", "error": "unknown_integration"}
    integration = connect_pcl_integration(
        source=source,
        name=config["name"],
        scopes=config["scopes"],
        metadata=payload.metadata,
    )
    return {"status": "connected", "integration": integration}


@app.post("/pcl/integrations/{source}/disconnect")
async def disconnect_pcl_integration_endpoint(source: str):
    disconnected = disconnect_pcl_integration(source)
    return {"status": "disconnected" if disconnected else "not_found_or_already_disconnected"}


@app.delete("/pcl/integrations/{source}/data")
async def delete_pcl_integration_data_endpoint(source: str):
    deleted = delete_pcl_integration_data(source)
    return {"status": "deleted", "deleted": deleted}


@app.post("/pcl/integrations/{source}/sync")
async def sync_pcl_integration_endpoint(source: str):
    return sync_integration(source)


@app.post("/pcl/events/feature")
async def record_pcl_feature_event(payload: PclFeatureEventRequest):
    app_record = get_pcl_app(payload.app_id)
    if not app_record:
        return {"status": "error", "error": "unknown_app"}
    if app_record.get("status") != "active":
        return {"status": "error", "error": "app_revoked"}
    sanitized = strip_raw_content({
        "feature_id": payload.feature_id,
        "feature_name": payload.feature_name,
        "event_type": payload.event_type,
        "metadata": payload.metadata,
        "timestamp": payload.timestamp,
    })
    event = insert_pcl_feature_event(
        app_id=payload.app_id,
        user_id=payload.user_id,
        feature_id=str(sanitized.get("feature_id", payload.feature_id)),
        feature_name=str(sanitized.get("feature_name", payload.feature_name)),
        event_type=str(sanitized.get("event_type", payload.event_type)),
        weight=max(0.0, min(float(payload.weight), 5.0)),
        metadata={},
        timestamp=payload.timestamp,
    )
    return {"status": "ok", "event": event}


@app.post("/pcl/query")
async def query_personal_context(payload: PclQueryRequest):
    app_record = get_pcl_app(payload.app_id)
    allowed_layers, denial_reason = resolve_allowed_layers(
        app_record,
        payload.requested_layers,
    )
    feature_ids = [feature.feature_id for feature in payload.features]
    if denial_reason:
        log = insert_pcl_query_log(
            app_id=payload.app_id,
            user_id=payload.user_id,
            purpose=payload.purpose,
            requested_layers=payload.requested_layers,
            returned_layers=[],
            feature_ids=feature_ids,
            status="denied",
            reason=denial_reason,
        )
        return {"error": denial_reason, "audit": {"query_logged": True, "log_id": log["id"]}}

    profile = build_local_user_context_profile(payload.user_id)
    query = ContextQuery(
        app_id=payload.app_id,
        user_id=payload.user_id,
        purpose=payload.purpose,
        requested_layers=payload.requested_layers,
        features=payload.features,
    )
    bundle = compose_decision_bundle(query, profile, allowed_layers=allowed_layers)
    log = insert_pcl_query_log(
        app_id=payload.app_id,
        user_id=payload.user_id,
        purpose=payload.purpose,
        requested_layers=payload.requested_layers,
        returned_layers=bundle.allowed_layers,
        feature_ids=feature_ids,
        status="returned",
    )
    response = bundle.model_dump()
    response["audit"]["log_id"] = log["id"]
    return response


@app.post("/v1/ingest/sdk")
async def ingest_sdk_context_event(payload: ContextLayerEventRequest):
    return ingest_context_event(payload.model_dump(exclude_none=True), source="sdk")


@app.post("/v1/ingest/extension")
async def ingest_extension_context_event(payload: ContextLayerEventRequest):
    return ingest_context_event(payload.model_dump(exclude_none=True), source="extension")


@app.post("/v1/context/bundle")
async def get_contextlayer_bundle(
    payload: ContextBundleRequest,
    authorization: Optional[str] = Header(default=""),
    x_user_token: Optional[str] = Header(default=""),
):
    authz = authorize_developer_context_request(
        authorization=authorization or "",
        user_id=_resolve_context_user_id(payload.user_id, x_user_token or ""),
        app_id=payload.app_id,
        requested_scopes=payload.requested_scopes,
    )
    if not authz["authorized"]:
        return authz
    user_id = _resolve_context_user_id(payload.user_id, x_user_token or "")
    return build_context_bundle(
        user_id=user_id,
        app_id=payload.app_id,
        intent=payload.intent,
        requested_scopes=payload.requested_scopes,
        source="rest",
    ) | {"auth": authz}


@app.post("/v1/context/feedback")
async def record_contextlayer_feedback(payload: ContextFeedbackRequest):
    if payload.outcome not in {"accepted", "rejected", "modified"}:
        return {"status": "error", "error": "invalid_outcome"}
    return apply_context_feedback(
        user_id=payload.user_id,
        bundle_id=payload.bundle_id,
        app_id=payload.app_id,
        outcome=payload.outcome,
        features_actually_used=payload.features_actually_used,
    )


@app.post("/v1/context/heartbeat")
async def record_contextlayer_heartbeat(payload: ContextHeartbeatRequest):
    return update_active_context(
        user_id=payload.user_id,
        project=payload.project or "",
        active_apps=payload.active_apps,
        inferred_intent=payload.inferred_intent or "",
        session_depth=payload.session_depth,
    )


@app.get("/v1/context/activity")
async def get_contextlayer_activity_endpoint(user_id: str = "local_user", limit: int = 100):
    return get_contextlayer_activity(user_id=user_id, limit=limit)


@app.get("/v1/context/privacy-drops")
async def get_contextlayer_privacy_drops(
    user_id: Optional[str] = None,
    limit: int = 100,
):
    return {
        "user_id": user_id,
        "drops": list_privacy_filter_drops(user_id=user_id, limit=limit),
    }


@app.post("/v1/context/raw-events/cleanup")
async def cleanup_contextlayer_raw_events(payload: RawEventCleanupRequest):
    from datetime import datetime, timedelta

    older_than_days = max(1, min(int(payload.older_than_days), 365))
    older_than_ms = int((datetime.now() - timedelta(days=older_than_days)).timestamp() * 1000)
    deleted = delete_old_raw_context_events(
        user_id=payload.user_id,
        older_than_ms=older_than_ms,
    )
    return {
        "status": "ok",
        "user_id": payload.user_id,
        "older_than_days": older_than_days,
        "deleted": deleted,
    }


@app.get("/v1/context/feature-signals")
async def get_contextlayer_feature_signals(
    user_id: str = "local_user",
    app_id: Optional[str] = None,
    active_only: bool = True,
):
    return {
        "user_id": user_id,
        "app_id": app_id,
        "features": list_feature_signals(
            user_id=user_id,
            app_id=app_id,
            active_only=active_only,
        ),
    }


@app.delete("/v1/context/all")
async def delete_contextlayer_all(user_id: str = "local_user"):
    return hard_delete_contextlayer_user(user_id)


@app.post("/v1/chat/completions")
async def contextlayer_chat_completions(
    payload: ChatCompletionRequest,
    authorization: Optional[str] = Header(default=""),
    x_user_id: Optional[str] = Header(default="local_user"),
    x_app_id: Optional[str] = Header(default="human_api_proxy"),
    x_user_token: Optional[str] = Header(default=""),
    x_contextlayer_api_key: Optional[str] = Header(default=""),
):
    data = payload.model_dump(exclude_none=True)
    user_id = _resolve_context_user_id(payload.user_id or x_user_id or "local_user", x_user_token or "")
    app_id = payload.app_id or x_app_id or "human_api_proxy"
    data.pop("user_id", None)
    data.pop("app_id", None)
    context_authorization = (
        f"Bearer {x_contextlayer_api_key}"
        if x_contextlayer_api_key
        else ""
    )
    return await proxy_chat_completion(
        data,
        user_id=user_id,
        app_id=app_id,
        authorization=authorization or "",
        context_authorization=context_authorization,
    )


@app.post("/v1/assistant/chat")
async def contextlayer_assistant_chat(
    payload: AssistantChatRequest,
    authorization: Optional[str] = Header(default=""),
):
    return await personal_assistant_chat(
        message=payload.message,
        user_id=payload.user_id,
        model=payload.model,
        authorization=authorization or "",
    )


@app.post("/v1/jobs/daily-refresh")
async def run_contextlayer_daily_refresh(payload: DailyRefreshRequest):
    return run_daily_refresh(
        user_id=payload.user_id,
        timezone=payload.timezone,
        job_id=payload.job_id,
        step_completed=payload.step_completed,
    )


@app.get("/v1/jobs/daily-refresh")
async def list_contextlayer_daily_refresh_jobs(
    user_id: Optional[str] = None,
    limit: int = 100,
):
    return {"jobs": list_daily_refresh_jobs(user_id=user_id, limit=limit)}


@app.post("/v1/jobs/daily-refresh/due")
async def run_due_contextlayer_daily_refreshes(payload: DueDailyRefreshRequest):
    from datetime import datetime

    now = datetime.fromisoformat(payload.now) if payload.now else None
    return run_due_daily_refreshes(now=now)


@app.get("/v1/context/brief")
async def get_contextlayer_brief(user_id: str = "local_user"):
    profile = get_user_profile_record(user_id)
    if not profile:
        return {
            "user_id": user_id,
            "context_brief": "",
            "daily_insight": "",
            "last_refresh_at": None,
            "last_synthesized_at": None,
            "timezone": "UTC",
        }
    return {
        "user_id": user_id,
        "context_brief": profile["context_brief"],
        "daily_insight": profile["daily_insight"],
        "last_refresh_at": profile["last_refresh_at"],
        "last_synthesized_at": profile["last_synthesized_at"],
        "timezone": profile["timezone"],
    }


@app.post("/v1/context/cold-start")
async def generate_contextlayer_cold_start(payload: ColdStartRequest):
    return generate_cold_start_signals(
        user_id=payload.user_id,
        app_id=payload.app_id,
        app_name=payload.app_name or payload.app_id,
        features=payload.features,
        role=payload.role or "",
        domain=payload.domain or "",
        skill_level=payload.skill_level or "intermediate",
    )


@app.post("/v1/auth/consent")
async def grant_contextlayer_consent(payload: ConsentRequest):
    permission = grant_app_consent(
        user_id=payload.user_id,
        app_id=payload.app_id,
        scopes=payload.scopes,
        developer_id=payload.developer_id or "",
        granted_via=payload.granted_via,
    )
    return {"status": "granted", "permission": permission}


@app.get("/v1/auth/consent")
async def list_contextlayer_consents(user_id: str = "local_user"):
    return {"user_id": user_id, "permissions": list_app_permissions(user_id)}


@app.delete("/v1/auth/consent/{app_id}")
async def revoke_contextlayer_consent(app_id: str, user_id: str = "local_user"):
    revoked = revoke_app_consent(user_id=user_id, app_id=app_id)
    return {"status": "revoked" if revoked else "not_found_or_already_revoked"}


@app.post("/v1/developer/register")
async def register_contextlayer_developer(payload: DeveloperRegistrationRequest):
    developer = upsert_developer(payload.email, payload.name or "")
    return {"status": "ok", "developer": developer}


@app.post("/v1/developer/apps")
async def register_contextlayer_developer_app(payload: DeveloperAppRequest):
    app_record = register_developer_app(
        developer_id=payload.developer_id,
        app_id=payload.app_id,
        name=payload.name,
        domain=payload.domain or "",
    )
    return {"status": "ok", "app": app_record}


@app.get("/v1/developer/keys")
async def list_contextlayer_developer_keys(developer_id: str):
    return {"keys": list_developer_api_keys(developer_id)}


@app.post("/v1/developer/keys")
async def create_contextlayer_developer_key(payload: DeveloperKeyRequest):
    key = create_developer_api_key(
        developer_id=payload.developer_id,
        app_id=payload.app_id or "",
        env=payload.env,
    )
    return {"status": "created", "api_key": key}


@app.post("/v1/jobs/profile-synthesize")
async def run_contextlayer_profile_synthesizer():
    return run_profile_synthesizer()


@app.post("/v1/jobs/memory/inductive")
async def run_contextlayer_inductive_job():
    return run_inductive_memory_job()


@app.post("/v1/jobs/memory/reflective")
async def run_contextlayer_reflective_job():
    return run_reflective_memory_job()


@app.post("/v1/jobs/memory/decay")
async def run_contextlayer_decay_job():
    return run_decay_engine()


class FeedEvent(BaseModel):
    source: str
    content_type: str
    content: str
    author: Optional[str] = ""
    url: Optional[str] = ""
    timestamp: int


@app.post("/feed-event")
async def receive_feed_event(event: FeedEvent):
    result = daemon.ingest_feed_activity(FeedActivityEvent(
        source=event.source,
        content_type=event.content_type,
        content=event.content,
        author=event.author or "",
        url=event.url or "",
        timestamp=event.timestamp,
    ))
    if result.status == "error":
        return {"status": "error", "error": result.reason}
    response = {"status": result.status}
    if result.reason:
        response["reason"] = result.reason
    return response


class ContextNegotiationRequest(BaseModel):
    platform_type: str
    facilities: list[str]
    requested_context: Optional[list[str]] = None
    purpose: Optional[str] = ""
    retention: Optional[str] = "session_only"


class PersonaFeedback(BaseModel):
    signal_type: str
    name: str
    action: str
    reason: Optional[str] = ""


@app.post("/context/negotiate")
async def negotiate_context(payload: ContextNegotiationRequest):
    return negotiate_context_contract(
        platform_type=payload.platform_type,
        facilities=payload.facilities,
        requested_context=payload.requested_context,
        purpose=payload.purpose or "",
        retention=payload.retention or "session_only",
    )


@app.get("/context/{contract_id}")
async def get_scoped_context(contract_id: str):
    return build_scoped_persona(contract_id)


@app.get("/context-contracts")
async def get_context_contracts(limit: int = 50):
    return {"contracts": list_context_contracts(limit=limit)}


@app.post("/context/{contract_id}/revoke")
async def revoke_context(contract_id: str):
    revoked = revoke_context_contract(contract_id)
    return {"status": "revoked" if revoked else "not_found_or_already_revoked"}


@app.get("/context-access-log")
async def get_context_access_log(contract_id: Optional[str] = None, limit: int = 100):
    return {"logs": get_context_access_logs(contract_id=contract_id, limit=limit)}


@app.post("/persona/feedback")
async def add_persona_feedback(payload: PersonaFeedback):
    allowed_actions = {"confirm", "reject", "hide", "boost"}
    if payload.action not in allowed_actions:
        return {"status": "error", "error": "unknown feedback action"}
    feedback = insert_persona_feedback(
        signal_type=payload.signal_type,
        name=payload.name,
        action=payload.action,
        reason=payload.reason or "",
    )
    return {"status": "ok", "feedback": feedback}


@app.post("/github/sync")
async def sync_github(payload: dict):
    username = payload.get("username", "").strip()
    if not username:
        return {"status": "error", "error": "username required"}
    try:
        from collectors.github import collect_github
        count = collect_github(username)
        return {"status": "ok", "items_saved": count}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@app.post("/extract")
async def trigger_extraction():
    from persona import extract_persona
    try:
        persona = extract_persona()
        if persona:
            return {"status": "ok"}
        return {"status": "error", "error": "No events to analyze"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
