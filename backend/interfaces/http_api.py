# backend/interfaces/http_api.py
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import FastAPI, Header, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

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
    grant_web_domain_permission,
    get_user_profile_record,
    check_web_domain_permission,
    list_app_permissions,
    list_web_domain_permissions,
    list_notification_routes,
    list_daily_refresh_jobs,
    list_feature_signals,
    list_privacy_filter_drops,
    list_developer_api_keys,
    list_developer_api_key_audit_logs,
    list_push_tokens,
    list_sync_devices,
    list_sync_conflicts,
    list_sync_audit_logs,
    get_context_access_logs,
    get_pcl_app,
    get_pcl_skill,
    get_pcl_feature_usage,
    get_pcl_onboarding_seed,
    get_waitlist_count,
    list_memory_source_settings,
    list_observability_events as list_observability_event_rows,
    insert_persona_feedback,
    insert_pcl_query_log,
    insert_pcl_feature_event,
    list_context_contracts,
    list_pcl_apps,
    list_pcl_skills,
    list_pcl_integrations,
    list_pcl_integration_oauth_tokens,
    list_pcl_query_logs,
    create_developer_api_key,
    revoke_developer_api_key,
    rotate_developer_api_key,
    check_developer_rate_limit,
    delete_old_raw_context_events,
    register_pcl_app,
    register_developer_app,
    register_push_token,
    upsert_pcl_skill,
    revoke_pcl_app,
    disable_pcl_skill,
    revoke_pcl_integration_oauth_token,
    revoke_context_contract,
    revoke_app_consent,
    revoke_push_token,
    revoke_web_domain_permission,
    save_pcl_onboarding_seed,
    set_memory_source_enabled,
    upsert_developer,
    update_pcl_integration_sync,
    get_user_preferences,
    upsert_user_preferences,
    insert_privacy_boundary,
    list_privacy_boundaries,
    delete_privacy_boundary,
    get_context_sharing_preview,
    list_context_sharing_previews,
    decide_context_sharing_preview,
    search_persona_signals,
    update_persona_signal,
    get_persona_signal_by_id,
    delete_persona_signal,
    export_user_context_data,
    get_unified_permissions,
    insert_control_center_audit,
    list_control_center_audit,
)
from living_persona import build_living_persona
from context_packaging import build_context_package, create_context_contract
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
from pcl.privacy import contains_blocked_secret, sanitize_integration_metadata
from pcl.integrations import default_integration, integration_catalog
from pcl.integration_jobs import sync_due_integrations, sync_integration
from pcl.oauth import complete_oauth_flow, refresh_oauth_token, start_oauth_flow
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
from pcl.skill_router import route_skill_request
from pcl.memory import (
    append_memory_entry,
    decay_memory_confidence,
    delete_memory_file,
    ensure_default_memory_files,
    list_memory_files,
    read_memory_file,
    search_memory,
    write_memory_file,
)
from pcl.persona_diffs import (
    apply_memory_diff,
    approve_memory_diff,
    get_memory_diffs,
    propose_memory_diff,
    reject_memory_diff,
)
from pcl.messaging_bridge import ingest_messaging_event
from pcl.device_sync import (
    approve_pairing_session,
    claim_pairing_transfer,
    compact_sync_snapshots,
    create_sync_snapshot,
    generate_device_keypair,
    get_pairing_session,
    import_sync_snapshot,
    list_sync_state,
    register_pending_sync_device,
    resolve_sync_conflict,
    revoke_sync_device_with_recovery,
    rotate_sync_device_key,
    start_pairing_session,
    revoke_sync_device,
    trust_sync_device,
)
from pcl.observability import record_observability_event
from pcl.cold_start import generate_cold_start_signals
from pcl.daily_refresh import run_daily_refresh, run_due_daily_refreshes
from pcl.proxy import proxy_chat_completion
from pcl.shared_context import read_shared_context_bundle, shared_context_bundle_path
from predictions import predict_next_context
from scheduler import create_scheduler, start_background_collectors
from settings import csv_env, is_production_env, max_request_bytes, validate_production_config
from pcl.control_center import (
    get_control_center_summary,
    search_signals,
    edit_signal,
    remove_signal,
    get_signal_detail,
    export_user_data,
    get_unified_permission_list,
    revoke_permission_by_id,
    get_control_center_audit_log,
)
from pcl.context_preview import (
    generate_context_preview,
    handle_preview_decision,
    get_preview_history,
)
from pcl.privacy_boundaries import (
    get_onboarding_questions,
    save_onboarding_flow_answers,
    get_user_privacy_profile,
    add_privacy_boundary,
    remove_privacy_boundary,
    deactivate_privacy_boundary,
    check_sharing_allowed,
)
from pcl.egress import enforce_egress_policy
from pcl.auth import (
    require_local_auth,
    create_bootstrap_session,
    install_secret_log_redaction,
    local_auth_enabled,
    AuthError,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    install_secret_log_redaction()
    validate_production_config()
    create_tables()
    scheduler = create_scheduler()
    scheduler.start()
    start_background_collectors()
    yield
    scheduler.shutdown()


app = FastAPI(title="PersonaLayer", lifespan=lifespan)

_CORS_METHODS = "POST, GET, PATCH, DELETE, OPTIONS"
_CORS_HEADERS = "Content-Type, Authorization, x-user-token, x-contextlayer-api-key, x-upstream-api-key, x-csrf-token"
_DEFAULT_ALLOWED_ORIGINS = {
    "http://localhost:7823",
    "http://127.0.0.1:7823",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
}
_PUBLIC_PATHS = {
    "/health",
    "/waitlist",
    "/waitlist/count",
    "/pcl/onboarding/questions",
    "/pcl/integrations/catalog",
    "/v1/auth/local/session",
}
_PUBLIC_PREFIXES = ("/landing", "/dashboard")
_EXTENSION_INGEST_PATHS = {"/v1/ingest/extension", "/event"}
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    for name, value in _SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    if is_production_env():
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.middleware("http")
async def request_size_limit(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > max_request_bytes():
                return Response(
                    status_code=413,
                    content=json.dumps({"error": "payload_too_large"}),
                    media_type="application/json",
                )
        except ValueError:
            return Response(
                status_code=400,
                content=json.dumps({"error": "invalid_content_length"}),
                media_type="application/json",
            )
    return await call_next(request)


@app.middleware("http")
async def scoped_local_cors(request: Request, call_next):
    origin = request.headers.get("origin", "")
    cors_allowed = _is_cors_origin_allowed(origin)
    if request.method == "OPTIONS" and origin:
        if not cors_allowed:
            return Response(status_code=403)
        response = Response(status_code=204)
    else:
        response = await call_next(request)
    if cors_allowed:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = _CORS_METHODS
        response.headers["Access-Control-Allow-Headers"] = _CORS_HEADERS
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
    return response


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Enforce local auth on sensitive endpoints."""
    if not local_auth_enabled():
        return await call_next(request)
    path = request.url.path
    if path in _PUBLIC_PATHS or any(path.startswith(prefix) for prefix in _PUBLIC_PREFIXES):
        return await call_next(request)

    # Allow extension origins without session token for ingest (they have domain checks)
    origin = request.headers.get("origin", "")
    if origin and not _is_cors_origin_allowed(origin):
        return Response(
            status_code=403,
            content=json.dumps({"error": "forbidden_origin"}),
            media_type="application/json",
        )
    if _is_extension_origin_allowed(origin):
        if path in _EXTENSION_INGEST_PATHS:
            return await call_next(request)

    # ContextLayer developer API keys are authorized inside the endpoint because
    # they must be checked against app ownership and user consent, not local
    # dashboard sessions. Do not consume a cl_* key as a local session token.
    auth_header = request.headers.get("authorization", "")
    bearer = (auth_header[7:] if auth_header.lower().startswith("bearer ") else auth_header).strip()
    if path == "/v1/context/bundle" and bearer.startswith("cl_"):
        return await call_next(request)

    # Check session for everything else
    try:
        token = (auth_header[7:] if auth_header.lower().startswith("bearer ") else auth_header).strip()
        if not token:
            cookie = request.headers.get("cookie", "")
            for part in cookie.split(";"):
                part = part.strip()
                if part.startswith("pl_session="):
                    token = part[len("pl_session="):]
                    break
        if token:
            session = require_local_auth(token)
            request.state.user_id = session["user_id"]
        else:
            raise AuthError("missing_session_token")
    except AuthError:
        if request.method == "OPTIONS":
            return await call_next(request)
        return Response(
            status_code=401,
            content=json.dumps({"error": "unauthorized", "detail": "Invalid or missing session"}),
            media_type="application/json",
        )
    return await call_next(request)


def _is_cors_origin_allowed(origin: str) -> bool:
    if not origin:
        return False
    if origin in _allowed_http_origins():
        return True
    if _is_extension_origin_allowed(origin):
        return True
    return False


def _allowed_http_origins() -> set[str]:
    configured = csv_env("PERSONALAYER_ALLOWED_ORIGINS")
    configured.discard("*")
    if configured:
        return configured
    return set() if is_production_env() else set(_DEFAULT_ALLOWED_ORIGINS)


def _allowed_extension_origins() -> set[str]:
    configured = csv_env("PERSONALAYER_EXTENSION_ORIGINS")
    configured.discard("*")
    return configured


def _is_extension_origin_allowed(origin: str) -> bool:
    allowed = _allowed_extension_origins()
    if allowed:
        return origin in allowed
    if is_production_env():
        return False
    parsed = urlparse(origin)
    scheme = (parsed.scheme or "").lower()
    if scheme in {"chrome-extension", "safari-web-extension"}:
        return True
    return False

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


class LocalSessionRequest(BaseModel):
    user_id: str = "local_user"
    bootstrap_token: str = ""


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


@app.post("/v1/auth/local/session")
async def create_local_auth_session(payload: LocalSessionRequest, response: Response):
    try:
        token = create_bootstrap_session(payload.user_id or "local_user", payload.bootstrap_token)
    except AuthError as exc:
        return Response(
            status_code=401,
            content=json.dumps({"error": "unauthorized", "detail": str(exc)}),
            media_type="application/json",
        )
    response.set_cookie(
        "pl_session",
        token,
        httponly=True,
        samesite="strict",
        secure=os.getenv("PERSONALAYER_COOKIE_SECURE", "0") == "1",
        max_age=60 * 60 * 24 * 7,
    )
    body = {"status": "ok", "user_id": payload.user_id or "local_user"}
    if os.getenv("PERSONALAYER_RETURN_SESSION_TOKEN", "0") == "1" or not is_production_env():
        body["session_token"] = token
    return body


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


class PclSkillRegistration(BaseModel):
    skill_id: str
    name: str
    category: str = "general"
    description: str = ""
    instructions: str = ""
    allowed_layers: list[ContextLayer] = []
    memory_scopes: list[str] = []
    required_tools: list[str] = []
    privacy_rules: list[str] = []


class PclSkillRouteRequest(BaseModel):
    user_id: str = "local_user"
    message: str
    intent: str = ""
    category: Optional[str] = None
    max_skills: int = 3
    include_memory: bool = False


class MemoryWriteRequest(BaseModel):
    user_id: str = "local_user"
    content: str
    source: str = "manual"
    reason: str = ""


class MemoryAppendRequest(BaseModel):
    user_id: str = "local_user"
    entry: str
    heading: Optional[str] = None
    source: str = "manual"
    reason: str = ""


class MemorySearchRequest(BaseModel):
    user_id: str = "local_user"
    query: str
    scopes: Optional[list[str]] = None
    limit: int = 10


class MemoryQualityDecayRequest(BaseModel):
    user_id: str = "local_user"
    scopes: Optional[list[str]] = None


class MemoryDiffRequest(BaseModel):
    user_id: str = "local_user"
    scope: str
    proposed_content: str
    reason: str = ""
    source: str = "manual"
    auto_apply: bool = True


class MemoryDiffDecisionRequest(BaseModel):
    reviewer_note: str = ""


class MemoryForgetRequest(BaseModel):
    user_id: str = "local_user"
    reason: str = ""


class MemorySourceToggleRequest(BaseModel):
    user_id: str = "local_user"
    enabled: bool
    reason: str = ""


class MessagingEventRequest(BaseModel):
    user_id: str = "local_user"
    sender: str
    text: str
    thread_id: str = ""
    timestamp: Optional[int] = None


class SyncDeviceRequest(BaseModel):
    user_id: str = "local_user"
    device_id: str
    device_name: str = ""
    public_key: str = ""
    requested_scopes: list[str] = Field(default_factory=list)


class SyncDeviceTrustRequest(BaseModel):
    user_id: str = "local_user"
    device_name: str = ""
    public_key: str = ""


class SyncImportRequest(BaseModel):
    user_id: str = "local_user"
    remote_device_id: str
    encrypted_blob: str
    expected_parent_version: Optional[str] = None


class SyncConflictResolutionRequest(BaseModel):
    user_id: str = "local_user"
    action: str
    device_id: str = ""


class SyncCompactRequest(BaseModel):
    user_id: str = "local_user"
    keep_per_device: int = 5


class SyncPairingStartRequest(BaseModel):
    user_id: str = "local_user"
    requester_device_id: str
    requester_device_name: str = ""
    requester_public_key: str
    requested_scopes: list[str] = Field(default_factory=list)
    ttl_seconds: int = 600


class SyncPairingApprovalRequest(BaseModel):
    user_id: str = "local_user"
    pairing_code: str = ""
    session_id: str = ""
    approver_device_id: str
    approver_device_name: str = ""
    approver_public_key: str = ""


class SyncPairingClaimRequest(BaseModel):
    user_id: str = "local_user"
    requester_device_id: str
    requester_private_key: str = ""


class SyncDeviceKeyRotationRequest(BaseModel):
    user_id: str = "local_user"
    public_key: str
    recovery_token: str = ""


class SyncDeviceRecoveryRevokeRequest(BaseModel):
    user_id: str = "local_user"
    reason: str = ""


class ObservabilityEventRequest(BaseModel):
    user_id: str = "local_user"
    source: str
    event_name: str
    severity: str = "info"
    route: str = ""
    status_code: Optional[int] = None
    duration_ms: Optional[int] = None
    attributes: dict = {}


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
    account_hint: Optional[str] = ""
    auth_status: Optional[str] = "local_metadata"
    auth_expires_at: Optional[int] = None


class PclIntegrationOAuthStartRequest(BaseModel):
    user_id: str = "local_user"
    redirect_uri: str = "http://127.0.0.1:7824/pcl/integrations/oauth/callback"


class PclIntegrationOAuthCallbackRequest(BaseModel):
    state: str
    code: str
    account_hint: Optional[str] = ""
    token_response: Optional[dict] = None


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


class WebDomainPermissionRequest(BaseModel):
    user_id: str = "local_user"
    domain: str
    scopes: list[str] = ["getFeatureUsage", "track"]


class WebDomainPermissionCheckRequest(BaseModel):
    user_id: str = "local_user"
    domain: str
    requested_scopes: list[str] = []


class DevicePushTokenRequest(BaseModel):
    user_id: str = "local_user"
    device_id: str
    apns_token: str
    platform: str = "ios"
    environment: str = "development"


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


class DeveloperKeyLifecycleRequest(BaseModel):
    developer_id: str


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


@app.post("/pcl/skills")
async def register_personal_context_skill(payload: PclSkillRegistration):
    return upsert_pcl_skill(
        skill_id=payload.skill_id,
        name=payload.name,
        category=payload.category,
        description=payload.description,
        instructions=payload.instructions,
        allowed_layers=payload.allowed_layers,
        memory_scopes=payload.memory_scopes,
        required_tools=payload.required_tools,
        privacy_rules=payload.privacy_rules,
    )


@app.get("/pcl/skills")
async def get_personal_context_skills(
    category: Optional[str] = None,
    active_only: bool = True,
    limit: int = 100,
):
    return {
        "skills": list_pcl_skills(
            category=category,
            active_only=active_only,
            limit=limit,
        )
    }


@app.post("/pcl/skills/route")
async def route_personal_context_skills(payload: PclSkillRouteRequest):
    return route_skill_request(
        message=payload.message,
        intent=payload.intent,
        category=payload.category,
        max_skills=payload.max_skills,
        user_id=payload.user_id,
        include_memory=payload.include_memory,
    )


@app.get("/pcl/skills/{skill_id}")
async def get_personal_context_skill(skill_id: str):
    skill = get_pcl_skill(skill_id)
    return skill or {"error": "not_found"}


@app.post("/pcl/skills/{skill_id}/disable")
async def disable_personal_context_skill(skill_id: str):
    disabled = disable_pcl_skill(skill_id)
    return {"status": "disabled" if disabled else "not_found_or_already_disabled"}


@app.post("/v1/memory/init")
async def initialize_memory_files(user_id: str = "local_user"):
    return ensure_default_memory_files(user_id)


@app.get("/v1/memory/files")
async def get_memory_files(user_id: str = "local_user"):
    return {"user_id": user_id, "files": list_memory_files(user_id)}


@app.post("/v1/memory/search")
async def search_memory_endpoint(payload: MemorySearchRequest):
    return search_memory(
        user_id=payload.user_id,
        query=payload.query,
        scopes=payload.scopes,
        limit=payload.limit,
    )


@app.post("/v1/memory/quality/decay")
async def decay_memory_quality_endpoint(payload: MemoryQualityDecayRequest):
    return decay_memory_confidence(user_id=payload.user_id, scopes=payload.scopes)


@app.post("/v1/memory/diffs")
async def propose_memory_diff_endpoint(payload: MemoryDiffRequest):
    return propose_memory_diff(
        user_id=payload.user_id,
        scope=payload.scope,
        proposed_content=payload.proposed_content,
        reason=payload.reason,
        source=payload.source,
        auto_apply=payload.auto_apply,
    )


@app.get("/v1/memory/diffs")
async def list_memory_diffs_endpoint(
    user_id: str = "local_user",
    status: Optional[str] = None,
    limit: int = 100,
):
    return get_memory_diffs(user_id=user_id, status=status, limit=limit)


@app.post("/v1/memory/diffs/{diff_id}/approve")
async def approve_memory_diff_endpoint(diff_id: str, payload: MemoryDiffDecisionRequest):
    return approve_memory_diff(diff_id, reviewer_note=payload.reviewer_note)


@app.post("/v1/memory/diffs/{diff_id}/reject")
async def reject_memory_diff_endpoint(diff_id: str, payload: MemoryDiffDecisionRequest):
    return reject_memory_diff(diff_id, reviewer_note=payload.reviewer_note)


@app.post("/v1/memory/diffs/{diff_id}/apply")
async def apply_memory_diff_endpoint(diff_id: str, payload: MemoryDiffDecisionRequest):
    return apply_memory_diff(diff_id, reviewer_note=payload.reviewer_note)


@app.get("/v1/memory/sources")
async def list_memory_sources(user_id: str = "local_user"):
    return {"user_id": user_id, "sources": list_memory_source_settings(user_id)}


@app.put("/v1/memory/sources/{source}")
async def toggle_memory_source(source: str, payload: MemorySourceToggleRequest):
    setting = set_memory_source_enabled(
        user_id=payload.user_id,
        source=source,
        enabled=payload.enabled,
        reason=payload.reason,
    )
    insert_control_center_audit(
        user_id=payload.user_id,
        action="memory_source_toggled",
        target_type="memory_source",
        target_id=source,
        details={"enabled": payload.enabled, "reason": payload.reason},
    )
    return setting


@app.get("/v1/memory/{scope}")
async def get_memory_scope(scope: str, user_id: str = "local_user"):
    return read_memory_file(user_id, scope)


@app.put("/v1/memory/{scope}")
async def put_memory_scope(scope: str, payload: MemoryWriteRequest):
    return write_memory_file(
        payload.user_id,
        scope,
        payload.content,
        source=payload.source,
        reason=payload.reason,
    )


@app.post("/v1/memory/{scope}/append")
async def append_memory_scope(scope: str, payload: MemoryAppendRequest):
    return append_memory_entry(
        payload.user_id,
        scope,
        payload.entry,
        payload.heading,
        source=payload.source,
        reason=payload.reason,
    )


@app.delete("/v1/memory/{scope}")
async def delete_memory_scope(scope: str, payload: MemoryForgetRequest):
    return delete_memory_file(payload.user_id, scope, reason=payload.reason)


@app.post("/v1/messaging/{source}/messages")
async def ingest_message_bridge_event(source: str, payload: MessagingEventRequest):
    try:
        return ingest_messaging_event(
            source=source,
            user_id=payload.user_id,
            sender=payload.sender,
            text=payload.text,
            thread_id=payload.thread_id,
            timestamp=payload.timestamp,
        )
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}


@app.get("/v1/sync/state")
async def get_device_sync_state(user_id: str = "local_user"):
    return list_sync_state(user_id)


@app.post("/v1/sync/keypair")
async def create_device_sync_keypair():
    return generate_device_keypair()


@app.post("/v1/sync/pairing/start")
async def start_device_sync_pairing(payload: SyncPairingStartRequest):
    return start_pairing_session(
        user_id=payload.user_id,
        requester_device_id=payload.requester_device_id,
        requester_device_name=payload.requester_device_name,
        requester_public_key=payload.requester_public_key,
        requested_scopes=payload.requested_scopes or None,
        ttl_seconds=payload.ttl_seconds,
    )


@app.get("/v1/sync/pairing/{session_id}")
async def get_device_sync_pairing(session_id: str, user_id: str = "local_user"):
    return get_pairing_session(user_id=user_id, session_id=session_id)


@app.post("/v1/sync/pairing/approve")
async def approve_device_sync_pairing(payload: SyncPairingApprovalRequest):
    return approve_pairing_session(
        user_id=payload.user_id,
        pairing_code=payload.pairing_code,
        session_id=payload.session_id,
        approver_device_id=payload.approver_device_id,
        approver_device_name=payload.approver_device_name,
        approver_public_key=payload.approver_public_key,
    )


@app.post("/v1/sync/pairing/{session_id}/claim")
async def claim_device_sync_pairing(session_id: str, payload: SyncPairingClaimRequest):
    return claim_pairing_transfer(
        user_id=payload.user_id,
        session_id=session_id,
        requester_device_id=payload.requester_device_id,
        requester_private_key=payload.requester_private_key,
    )


@app.get("/v1/sync/devices")
async def get_sync_devices(user_id: str = "local_user"):
    return {"user_id": user_id, "devices": list_sync_devices(user_id)}


@app.post("/v1/sync/devices")
async def register_pending_device_sync_device(payload: SyncDeviceRequest):
    return register_pending_sync_device(
        user_id=payload.user_id,
        device_id=payload.device_id,
        device_name=payload.device_name,
        public_key=payload.public_key,
    )


@app.post("/v1/sync/devices/{device_id}/trust")
async def trust_device_sync_device(device_id: str, payload: SyncDeviceTrustRequest):
    return trust_sync_device(
        user_id=payload.user_id,
        device_id=device_id,
        device_name=payload.device_name,
        public_key=payload.public_key,
    )


@app.post("/v1/sync/devices/{device_id}/revoke")
async def revoke_device_sync_device(device_id: str, payload: SyncDeviceTrustRequest):
    return revoke_sync_device(user_id=payload.user_id, device_id=device_id)


@app.post("/v1/sync/devices/{device_id}/rotate-key")
async def rotate_device_sync_device_key(device_id: str, payload: SyncDeviceKeyRotationRequest):
    return rotate_sync_device_key(
        user_id=payload.user_id,
        device_id=device_id,
        public_key=payload.public_key,
        recovery_token=payload.recovery_token,
    )


@app.post("/v1/sync/devices/{device_id}/recovery-revoke")
async def recovery_revoke_device_sync_device(device_id: str, payload: SyncDeviceRecoveryRevokeRequest):
    return revoke_sync_device_with_recovery(
        user_id=payload.user_id,
        device_id=device_id,
        reason=payload.reason,
    )


@app.post("/v1/sync/snapshot")
async def create_device_sync_snapshot(payload: SyncDeviceRequest):
    return create_sync_snapshot(
        user_id=payload.user_id,
        device_id=payload.device_id,
        device_name=payload.device_name,
        public_key=payload.public_key,
    )


@app.post("/v1/sync/import")
async def import_device_sync_snapshot(payload: SyncImportRequest):
    return import_sync_snapshot(
        user_id=payload.user_id,
        remote_device_id=payload.remote_device_id,
        encrypted_blob=payload.encrypted_blob,
        expected_parent_version=payload.expected_parent_version,
    )


@app.get("/v1/sync/conflicts")
async def get_sync_conflicts(user_id: str = "local_user", status: Optional[str] = "open", limit: int = 100):
    return {"user_id": user_id, "conflicts": list_sync_conflicts(user_id, status=status, limit=limit)}


@app.get("/v1/sync/audit")
async def get_sync_audit(user_id: str = "local_user", limit: int = 100):
    return {"user_id": user_id, "audit": list_sync_audit_logs(user_id, limit=limit)}


@app.post("/v1/sync/conflicts/{conflict_id}/resolve")
async def resolve_device_sync_conflict(conflict_id: str, payload: SyncConflictResolutionRequest):
    return resolve_sync_conflict(
        user_id=payload.user_id,
        conflict_id=conflict_id,
        action=payload.action,
        device_id=payload.device_id,
    )


@app.post("/v1/sync/snapshots/compact")
async def compact_device_sync_snapshots(payload: SyncCompactRequest):
    return compact_sync_snapshots(
        user_id=payload.user_id,
        keep_per_device=payload.keep_per_device,
    )


@app.get("/v1/observability/events")
async def get_observability_events(
    user_id: str = "local_user",
    source: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
):
    return {
        "user_id": user_id,
        "events": list_observability_event_rows(
            user_id=user_id,
            source=source,
            severity=severity,
            limit=limit,
        ),
    }


@app.post("/v1/observability/events")
async def create_observability_event(payload: ObservabilityEventRequest):
    return {
        "status": "recorded",
        "event": record_observability_event(
            user_id=payload.user_id,
            source=payload.source,
            event_name=payload.event_name,
            severity=payload.severity,
            route=payload.route,
            status_code=payload.status_code,
            duration_ms=payload.duration_ms,
            attributes=payload.attributes,
        ),
    }


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
                "sync_cursor": {},
                "next_sync_after": None,
                "account_hint": "",
                "auth_status": "not_connected",
                "auth_expires_at": None,
                "error": "",
                "connected_at": None,
                "disconnected_at": None,
            }),
        })
    return {"integrations": rows}


@app.get("/pcl/integrations/oauth/tokens")
async def get_pcl_integration_oauth_tokens(user_id: str = "local_user"):
    return {"user_id": user_id, "tokens": list_pcl_integration_oauth_tokens(user_id)}


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
        metadata=sanitize_integration_metadata(payload.metadata),
        account_hint=payload.account_hint or "",
        auth_status=payload.auth_status or "local_metadata",
        auth_expires_at=payload.auth_expires_at,
    )
    return {"status": "connected", "integration": integration}


@app.post("/pcl/integrations/{source}/oauth/start")
async def start_pcl_integration_oauth(source: str, payload: PclIntegrationOAuthStartRequest):
    return start_oauth_flow(
        source=source,
        user_id=payload.user_id,
        redirect_uri=payload.redirect_uri,
    )


@app.post("/pcl/integrations/oauth/callback")
async def complete_pcl_integration_oauth(payload: PclIntegrationOAuthCallbackRequest):
    return complete_oauth_flow(
        state=payload.state,
        code=payload.code,
        account_hint=payload.account_hint or "",
        token_response=payload.token_response,
    )


@app.delete("/pcl/integrations/{source}/oauth/token")
async def revoke_pcl_integration_oauth_token_endpoint(source: str, user_id: str = "local_user"):
    revoked = revoke_pcl_integration_oauth_token(source=source, user_id=user_id)
    return {"status": "revoked" if revoked else "not_found_or_already_revoked"}


@app.post("/pcl/integrations/{source}/oauth/refresh")
async def refresh_pcl_integration_oauth_token_endpoint(source: str, user_id: str = "local_user"):
    return refresh_oauth_token(source=source, user_id=user_id)


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


@app.post("/pcl/integrations/sync-due")
async def sync_due_pcl_integrations_endpoint(user_id: str = "local_user"):
    return sync_due_integrations(user_id=user_id)


@app.post("/pcl/events/feature")
async def record_pcl_feature_event(payload: PclFeatureEventRequest):
    app_record = get_pcl_app(payload.app_id)
    if not app_record:
        return {"status": "error", "error": "unknown_app"}
    if app_record.get("status") != "active":
        return {"status": "error", "error": "app_revoked"}
    if contains_blocked_secret(payload.metadata):
        return {"status": "error", "error": "blocked_secret_detected"}
    event = insert_pcl_feature_event(
        app_id=payload.app_id,
        user_id=payload.user_id,
        feature_id=payload.feature_id,
        feature_name=payload.feature_name,
        event_type=payload.event_type,
        weight=max(0.0, min(float(payload.weight), 5.0)),
        metadata=payload.metadata,
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
    return enforce_egress_policy(
        response,
        user_id=payload.user_id,
        app_id=payload.app_id,
        requested_scopes=[layer.value if hasattr(layer, "value") else str(layer) for layer in payload.requested_layers],
        source="rest",
    )


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
    bundle = build_context_bundle(
        user_id=user_id,
        app_id=payload.app_id,
        intent=payload.intent,
        requested_scopes=payload.requested_scopes,
        source="rest",
    ) | {"auth": authz}
    return enforce_egress_policy(
        bundle,
        user_id=user_id,
        app_id=payload.app_id,
        requested_scopes=payload.requested_scopes,
        source="rest",
    )


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
    x_upstream_api_key: Optional[str] = Header(default=""),
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
        authorization=_upstream_authorization(x_upstream_api_key or ""),
        context_authorization=context_authorization,
    )


@app.post("/v1/assistant/chat")
async def contextlayer_assistant_chat(
    payload: AssistantChatRequest,
    authorization: Optional[str] = Header(default=""),
    x_upstream_api_key: Optional[str] = Header(default=""),
):
    return await personal_assistant_chat(
        message=payload.message,
        user_id=payload.user_id,
        model=payload.model,
        authorization=_upstream_authorization(x_upstream_api_key or ""),
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


@app.get("/v1/context/shared-bundle")
async def get_contextlayer_shared_bundle(user_id: str = "local_user"):
    path = shared_context_bundle_path(user_id)
    if not path.exists():
        return {"error": "shared_bundle_not_found", "user_id": user_id}
    try:
        bundle = read_shared_context_bundle(user_id)
    except ValueError as exc:
        return {"error": str(exc), "user_id": user_id}
    return enforce_egress_policy(
        {
            "status": "ok",
            "user_id": user_id,
            "bundle": bundle,
            "source": "local_shared_context_file",
        },
        user_id=user_id,
        app_id="shared_bundle",
        requested_scopes=["all"],
        source="rest",
    )


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


@app.post("/v1/web/permissions")
async def grant_contextlayer_web_permission(payload: WebDomainPermissionRequest):
    permission = grant_web_domain_permission(
        user_id=payload.user_id,
        domain=payload.domain,
        scopes=payload.scopes,
    )
    return {"status": "granted", "permission": permission}


@app.get("/v1/web/permissions")
async def list_contextlayer_web_permissions(user_id: str = "local_user"):
    return {"user_id": user_id, "permissions": list_web_domain_permissions(user_id)}


@app.post("/v1/web/permissions/check")
async def check_contextlayer_web_permission(payload: WebDomainPermissionCheckRequest):
    return check_web_domain_permission(
        user_id=payload.user_id,
        domain=payload.domain,
        requested_scopes=payload.requested_scopes,
    )


@app.delete("/v1/web/permissions/{domain}")
async def revoke_contextlayer_web_permission(domain: str, user_id: str = "local_user"):
    revoked = revoke_web_domain_permission(user_id=user_id, domain=domain)
    return {"status": "revoked" if revoked else "not_found_or_already_revoked"}


@app.post("/v1/devices/push-token")
async def register_contextlayer_push_token(payload: DevicePushTokenRequest):
    token = register_push_token(
        user_id=payload.user_id,
        device_id=payload.device_id,
        apns_token=payload.apns_token,
        platform=payload.platform,
        environment=payload.environment,
    )
    return enforce_egress_policy(
        {"status": "registered", "token": token},
        user_id=payload.user_id,
        app_id="push_token_service",
        requested_scopes=["device_management"],
        source="rest",
    )


@app.get("/v1/devices/push-token")
async def list_contextlayer_push_tokens(user_id: str = "local_user", active_only: bool = True):
    return enforce_egress_policy(
        {"user_id": user_id, "tokens": list_push_tokens(user_id=user_id, active_only=active_only)},
        user_id=user_id,
        app_id="push_token_service",
        requested_scopes=["device_management"],
        source="rest",
    )


@app.delete("/v1/devices/push-token/{device_id}")
async def revoke_contextlayer_push_token(device_id: str, user_id: str = "local_user"):
    revoked = revoke_push_token(user_id=user_id, device_id=device_id)
    return {"status": "revoked" if revoked else "not_found_or_already_revoked"}


@app.get("/v1/notifications/routes")
async def list_contextlayer_notification_routes(user_id: str = "local_user", limit: int = 100):
    return {"user_id": user_id, "routes": list_notification_routes(user_id=user_id, limit=limit)}


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


@app.get("/v1/developer/keys/audit")
async def list_contextlayer_developer_key_audit(developer_id: str, limit: int = 100):
    return {"developer_id": developer_id, "audit": list_developer_api_key_audit_logs(developer_id, limit=limit)}


@app.post("/v1/developer/keys")
async def create_contextlayer_developer_key(payload: DeveloperKeyRequest):
    rate = check_developer_rate_limit(payload.developer_id, "api_key_create", limit=10, window_seconds=60)
    if not rate["allowed"]:
        return {"status": "error", "error": "rate_limited", "rate_limit": rate}
    key = create_developer_api_key(
        developer_id=payload.developer_id,
        app_id=payload.app_id or "",
        env=payload.env,
    )
    return {"status": "created", "api_key": key}


@app.delete("/v1/developer/keys/{key_id}")
async def revoke_contextlayer_developer_key(key_id: str, payload: DeveloperKeyLifecycleRequest):
    rate = check_developer_rate_limit(payload.developer_id, "api_key_revoke", limit=30, window_seconds=60)
    if not rate["allowed"]:
        return {"status": "error", "error": "rate_limited", "rate_limit": rate}
    revoked = revoke_developer_api_key(key_id=key_id, developer_id=payload.developer_id)
    return {"status": "revoked" if revoked else "not_found_or_already_revoked"}


@app.post("/v1/developer/keys/{key_id}/rotate")
async def rotate_contextlayer_developer_key(key_id: str, payload: DeveloperKeyLifecycleRequest):
    rate = check_developer_rate_limit(payload.developer_id, "api_key_rotate", limit=10, window_seconds=60)
    if not rate["allowed"]:
        return {"status": "error", "error": "rate_limited", "rate_limit": rate}
    return rotate_developer_api_key(key_id=key_id, developer_id=payload.developer_id)


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
    return create_context_contract(
        platform_type=payload.platform_type,
        facilities=payload.facilities,
        requested_context=payload.requested_context,
        purpose=payload.purpose or "",
        retention=payload.retention or "session_only",
    )


@app.get("/context/{contract_id}")
async def get_scoped_context(contract_id: str):
    return build_context_package(contract_id)


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


class UserPreferencesRequest(BaseModel):
    user_id: str = "local_user"
    personalization_goals: list[str] = []
    privacy_level: str = "balanced"
    sharing_default: str = "ask"
    personalization_aggression: str = "medium"
    enabled_integrations: list[str] = []
    disabled_signal_sources: list[str] = []


class PrivacyBoundaryRequest(BaseModel):
    user_id: str = "local_user"
    boundary_type: str
    target: str
    reason: str = ""


class ContextPreviewRequest(BaseModel):
    user_id: str = "local_user"
    app_id: str
    app_name: str = ""
    requested_purpose: str = ""
    requested_layers: list[ContextLayer] = []
    requested_scopes: list[str] = []


class PreviewDecisionRequest(BaseModel):
    decision: str
    narrowed_fields: list[str] = []
    user_decision: str = ""


class SignalSearchRequest(BaseModel):
    user_id: str = "local_user"
    query: str = ""
    source: Optional[str] = None
    signal_type: Optional[str] = None
    shareable_only: bool = False
    limit: int = 100
    offset: int = 0


class SignalEditRequest(BaseModel):
    user_id: str = "local_user"
    name: Optional[str] = None
    weight: Optional[float] = None
    confidence: Optional[float] = None
    evidence: Optional[str] = None
    shareable: Optional[bool] = None
    reason: str = ""


class OnboardingFlowRequest(BaseModel):
    user_id: str = "local_user"
    answers: dict = {}


class RevokePermissionRequest(BaseModel):
    user_id: str = "local_user"
    permission_type: str


# ==================== Control Center Endpoints ====================

@app.get("/v1/control-center/summary")
async def control_center_summary(user_id: str = "local_user"):
    return get_control_center_summary(user_id)


@app.post("/v1/control-center/signals/search")
async def control_center_signal_search(payload: SignalSearchRequest):
    return search_signals(
        user_id=payload.user_id,
        query=payload.query,
        source=payload.source,
        signal_type=payload.signal_type,
        shareable_only=payload.shareable_only,
        limit=payload.limit,
        offset=payload.offset,
    )


@app.get("/v1/control-center/signals/{signal_id}")
async def control_center_signal_detail(signal_id: int, user_id: str = "local_user"):
    return get_signal_detail(user_id=user_id, signal_id=signal_id)


@app.patch("/v1/control-center/signals/{signal_id}")
async def control_center_signal_edit(signal_id: int, payload: SignalEditRequest):
    return edit_signal(
        user_id=payload.user_id,
        signal_id=signal_id,
        name=payload.name,
        weight=payload.weight,
        confidence=payload.confidence,
        evidence=payload.evidence,
        shareable=payload.shareable,
        reason=payload.reason,
    )


@app.delete("/v1/control-center/signals/{signal_id}")
async def control_center_signal_delete(signal_id: int, user_id: str = "local_user"):
    return remove_signal(user_id=user_id, signal_id=signal_id)


@app.post("/v1/control-center/export")
async def control_center_export(user_id: str = "local_user", format: str = "json"):
    return export_user_data(user_id=user_id, format=format)


@app.get("/v1/control-center/permissions")
async def control_center_permissions(user_id: str = "local_user"):
    return get_unified_permission_list(user_id)


@app.post("/v1/control-center/permissions/{permission_id}/revoke")
async def control_center_revoke_permission(permission_id: str, payload: RevokePermissionRequest):
    return revoke_permission_by_id(
        user_id=payload.user_id,
        permission_id=permission_id,
        permission_type=payload.permission_type,
    )


@app.get("/v1/control-center/audit")
async def control_center_audit(user_id: str = "local_user", limit: int = 100):
    return get_control_center_audit_log(user_id, limit=limit)


# ==================== Context Preview Endpoints ====================

@app.post("/v1/context/preview")
async def create_context_preview(payload: ContextPreviewRequest):
    return generate_context_preview(
        user_id=payload.user_id,
        app_id=payload.app_id,
        app_name=payload.app_name or payload.app_id,
        requested_purpose=payload.requested_purpose,
        requested_layers=payload.requested_layers,
        requested_scopes=payload.requested_scopes,
    )


@app.get("/v1/context/preview/{preview_id}")
async def get_context_preview(preview_id: str):
    preview = get_context_sharing_preview(preview_id)
    if not preview:
        return {"error": "preview_not_found"}
    return preview


@app.post("/v1/context/preview/{preview_id}/decision")
async def decide_context_preview(preview_id: str, payload: PreviewDecisionRequest):
    return handle_preview_decision(
        preview_id=preview_id,
        decision=payload.decision,
        narrowed_fields=payload.narrowed_fields,
        user_decision=payload.user_decision,
    )


@app.get("/v1/context/preview/history")
async def context_preview_history(user_id: str = "local_user", limit: int = 50):
    return get_preview_history(user_id=user_id, limit=limit)


# ==================== Privacy Boundaries Endpoints ====================

@app.get("/v1/onboarding/flow/questions")
async def get_onboarding_flow_questions():
    return {"questions": get_onboarding_questions()}


@app.post("/v1/onboarding/flow")
async def submit_onboarding_flow(payload: OnboardingFlowRequest):
    return save_onboarding_flow_answers(user_id=payload.user_id, answers=payload.answers)


@app.get("/v1/user/privacy-profile")
async def get_user_privacy_profile_endpoint(user_id: str = "local_user"):
    return get_user_privacy_profile(user_id)


@app.get("/v1/user/preferences")
async def get_user_preferences_endpoint(user_id: str = "local_user"):
    return get_user_preferences(user_id)


@app.put("/v1/user/preferences")
async def update_user_preferences_endpoint(payload: UserPreferencesRequest):
    return upsert_user_preferences(
        user_id=payload.user_id,
        personalization_goals=payload.personalization_goals,
        privacy_level=payload.privacy_level,
        sharing_default=payload.sharing_default,
        personalization_aggression=payload.personalization_aggression,
        enabled_integrations=payload.enabled_integrations,
        disabled_signal_sources=payload.disabled_signal_sources,
    )


@app.get("/v1/user/boundaries")
async def list_user_boundaries(user_id: str = "local_user", active_only: bool = True):
    return {"user_id": user_id, "boundaries": list_privacy_boundaries(user_id, active_only)}


@app.post("/v1/user/boundaries")
async def add_user_boundary(payload: PrivacyBoundaryRequest):
    return add_privacy_boundary(
        user_id=payload.user_id,
        boundary_type=payload.boundary_type,
        target=payload.target,
        reason=payload.reason,
    )


@app.delete("/v1/user/boundaries/{boundary_id}")
async def delete_user_boundary(boundary_id: str, user_id: str = "local_user"):
    return remove_privacy_boundary(user_id=user_id, boundary_id=boundary_id)


@app.post("/v1/user/boundaries/{boundary_id}/deactivate")
async def deactivate_user_boundary(boundary_id: str, user_id: str = "local_user"):
    return deactivate_privacy_boundary(user_id=user_id, boundary_id=boundary_id)


@app.post("/v1/context/check-sharing")
async def check_context_sharing(payload: ContextPreviewRequest):
    return check_sharing_allowed(
        user_id=payload.user_id,
        app_id=payload.app_id,
        fields=[str(l) for l in payload.requested_layers],
    )
