# backend/mcp_server.py
import asyncio
import json
import logging
from pathlib import Path
from dataclasses import dataclass

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp import types
except Exception as exc:
    logger_import_error = exc

    @dataclass
    class _Tool:
        name: str
        description: str
        inputSchema: dict

    @dataclass
    class _TextContent:
        type: str
        text: str

    class _Types:
        Tool = _Tool
        TextContent = _TextContent

    class _NoopServer:
        def __init__(self, name: str):
            self.name = name

        def list_tools(self):
            def decorator(func):
                return func
            return decorator

        def call_tool(self):
            def decorator(func):
                return func
            return decorator

    def Server(name: str):
        return _NoopServer(name)

    stdio_server = None
    types = _Types()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_PERSONA_FILE = str(Path.home() / ".personalayer" / "persona.json")

server = Server("personalayer")


# ── Pure handler functions (testable without MCP machinery) ──────────────────

def handle_get_persona(persona_file: str = DEFAULT_PERSONA_FILE) -> str:
    path = Path(persona_file)
    if not path.exists():
        return json.dumps({"error": "No persona data yet. Browse for 24h or run: python persona.py"})
    return path.read_text()


def handle_get_context(topic: str, persona_file: str = DEFAULT_PERSONA_FILE) -> str:
    path = Path(persona_file)
    if not path.exists():
        return json.dumps({"error": "No persona data yet."})

    persona = json.loads(path.read_text())
    topic_lower = topic.lower()

    depth_map = persona.get("interests", {}).get("depth", {})
    matched_depth = "unknown"
    for level, topics in depth_map.items():
        if any(topic_lower in t.lower() for t in topics):
            matched_depth = level
            break

    obsessions = [
        o for o in persona.get("interests", {}).get("obsessions", [])
        if topic_lower in o.lower()
    ]

    return json.dumps({
        "topic": topic,
        "depth": matched_depth,
        "related_obsessions": obsessions,
        "current_project": persona.get("identity", {}).get("current_project", "unknown"),
    }, indent=2)


def handle_get_current_focus(persona_file: str = DEFAULT_PERSONA_FILE) -> str:
    path = Path(persona_file)
    if not path.exists():
        return json.dumps({"error": "No persona data yet."})

    persona = json.loads(path.read_text())
    return json.dumps(persona.get("context", {}), indent=2)


def handle_negotiate_context(arguments: dict) -> str:
    from policy import negotiate_context_contract
    contract = negotiate_context_contract(
        platform_type=arguments.get("platform_type", "unknown"),
        facilities=arguments.get("facilities", []),
        requested_context=arguments.get("requested_context"),
        purpose=arguments.get("purpose", ""),
        retention=arguments.get("retention", "session_only"),
    )
    return json.dumps(contract, indent=2)


def handle_get_scoped_persona(contract_id: str) -> str:
    from policy import build_scoped_persona
    return json.dumps(build_scoped_persona(contract_id), indent=2)


def handle_revoke_context_contract(contract_id: str) -> str:
    from database import revoke_context_contract
    revoked = revoke_context_contract(contract_id)
    return json.dumps({"status": "revoked" if revoked else "not_found_or_already_revoked"}, indent=2)


def handle_list_context_contracts(limit: int = 20) -> str:
    from database import list_context_contracts
    return json.dumps({"contracts": list_context_contracts(limit=limit)}, indent=2)


def handle_record_persona_feedback(arguments: dict) -> str:
    from database import insert_persona_feedback
    action = arguments.get("action", "")
    if action not in {"confirm", "reject", "hide", "boost"}:
        return json.dumps({"status": "error", "error": "unknown feedback action"})
    feedback = insert_persona_feedback(
        signal_type=arguments.get("signal_type", ""),
        name=arguments.get("name", ""),
        action=action,
        reason=arguments.get("reason", ""),
    )
    return json.dumps({"status": "ok", "feedback": feedback}, indent=2)


def handle_get_living_persona() -> str:
    from living_persona import build_living_persona
    return json.dumps(build_living_persona(), indent=2)


def handle_predict_next_context(days: int = 14) -> str:
    from predictions import predict_next_context
    return json.dumps(predict_next_context(days=days), indent=2)


def handle_pcl_get_profile(user_id: str = "local_user") -> str:
    from pcl.profile import build_local_user_context_profile
    return json.dumps(build_local_user_context_profile(user_id).model_dump(), indent=2)


def handle_pcl_get_feature_usage(arguments: dict) -> str:
    from database import get_pcl_feature_usage
    return json.dumps({
        "user_id": arguments.get("user_id", "local_user"),
        "app_id": arguments.get("app_id"),
        "features": get_pcl_feature_usage(
            user_id=arguments.get("user_id", "local_user"),
            app_id=arguments.get("app_id"),
            days=arguments.get("days", 90),
        ),
    }, indent=2)


def handle_pcl_get_context(arguments: dict) -> str:
    from database import get_pcl_app, insert_pcl_query_log
    from pcl.composer import compose_decision_bundle
    from pcl.models import AppFeature, ContextQuery
    from pcl.permissions import resolve_allowed_layers
    from pcl.profile import build_local_user_context_profile

    app_id = arguments.get("app_id", "")
    user_id = arguments.get("user_id", "local_user")
    purpose = arguments.get("purpose", "ui_personalization")
    requested_layers = arguments.get("requested_layers", [])
    features = [
        AppFeature(**feature)
        for feature in arguments.get("features", [])
    ]
    feature_ids = [feature.feature_id for feature in features]
    app_record = get_pcl_app(app_id)
    allowed_layers, denial_reason = resolve_allowed_layers(app_record, requested_layers)
    if denial_reason:
        log = insert_pcl_query_log(
            app_id=app_id,
            user_id=user_id,
            purpose=purpose,
            requested_layers=requested_layers,
            returned_layers=[],
            feature_ids=feature_ids,
            status="denied",
            reason=denial_reason,
        )
        return json.dumps({"error": denial_reason, "audit": {"query_logged": True, "log_id": log["id"]}}, indent=2)

    query = ContextQuery(
        app_id=app_id,
        user_id=user_id,
        purpose=purpose,
        requested_layers=requested_layers,
        features=features,
    )
    bundle = compose_decision_bundle(
        query,
        build_local_user_context_profile(user_id),
        allowed_layers=allowed_layers,
    )
    log = insert_pcl_query_log(
        app_id=app_id,
        user_id=user_id,
        purpose=purpose,
        requested_layers=requested_layers,
        returned_layers=bundle.allowed_layers,
        feature_ids=feature_ids,
        status="returned",
    )
    response = bundle.model_dump()
    response["audit"]["log_id"] = log["id"]
    return json.dumps(response, indent=2)


def handle_pcl_get_constraints(user_id: str = "local_user") -> str:
    from pcl.profile import build_local_user_context_profile
    profile = build_local_user_context_profile(user_id)
    return json.dumps({
        "user_id": user_id,
        "constraints": {
            pref.key: pref.value
            for pref in profile.explicit_preferences
            if pref.hard_rule
        },
    }, indent=2)


def handle_contextlayer_get_bundle(arguments: dict) -> str:
    from pcl.contextlayer import authorize_developer_context_request, build_context_bundle
    user_id = _resolve_mcp_user_id(
        arguments.get("user_id", "local_user"),
        arguments.get("user_token", ""),
    )
    requested_scopes = arguments.get("requested_scopes", ["mcp"])
    auth = authorize_developer_context_request(
        authorization=_mcp_authorization(arguments),
        user_id=user_id,
        app_id=arguments.get("app_id", "mcp"),
        requested_scopes=requested_scopes,
    )
    if not auth["authorized"]:
        return json.dumps(auth, indent=2)
    return json.dumps(build_context_bundle(
        user_id=user_id,
        app_id=arguments.get("app_id", "mcp"),
        intent=arguments.get("intent", "full_profile"),
        requested_scopes=requested_scopes,
        source="mcp",
    ) | {"auth": auth}, indent=2)


def handle_contextlayer_get_feature_usage(arguments: dict) -> str:
    from database import list_feature_signals
    from pcl.contextlayer import authorize_developer_context_request
    user_id = _resolve_mcp_user_id(
        arguments.get("user_id", "local_user"),
        arguments.get("user_token", ""),
    )
    app_id = arguments.get("app_id") or "mcp"
    requested_scopes = arguments.get("requested_scopes", ["getFeatureUsage"])
    auth = authorize_developer_context_request(
        authorization=_mcp_authorization(arguments),
        user_id=user_id,
        app_id=app_id,
        requested_scopes=requested_scopes,
    )
    if not auth["authorized"]:
        return json.dumps(auth, indent=2)
    return json.dumps({
        "user_id": user_id,
        "app_id": app_id,
        "auth": auth,
        "features": list_feature_signals(
            user_id=user_id,
            app_id=app_id,
            active_only=arguments.get("active_only", True),
        ),
    }, indent=2)


def handle_contextlayer_get_active_context(arguments: dict | str = "local_user") -> str:
    from database import get_active_context
    from pcl.contextlayer import authorize_developer_context_request
    if isinstance(arguments, str):
        arguments = {"user_id": arguments}
    user_id = _resolve_mcp_user_id(
        arguments.get("user_id", "local_user"),
        arguments.get("user_token", ""),
    )
    app_id = arguments.get("app_id", "mcp")
    auth = authorize_developer_context_request(
        authorization=_mcp_authorization(arguments),
        user_id=user_id,
        app_id=app_id,
        requested_scopes=arguments.get("requested_scopes", ["getActiveContext"]),
    )
    if not auth["authorized"]:
        return json.dumps(auth, indent=2)
    return json.dumps({
        "user_id": user_id,
        "app_id": app_id,
        "auth": auth,
        "active_context": get_active_context(user_id),
    }, indent=2)


def handle_contextlayer_get_constraints(arguments: dict | str = "local_user") -> str:
    from pcl.contextlayer import authorize_developer_context_request
    if isinstance(arguments, str):
        arguments = {"user_id": arguments}
    user_id = _resolve_mcp_user_id(
        arguments.get("user_id", "local_user"),
        arguments.get("user_token", ""),
    )
    app_id = arguments.get("app_id", "mcp")
    auth = authorize_developer_context_request(
        authorization=_mcp_authorization(arguments),
        user_id=user_id,
        app_id=app_id,
        requested_scopes=arguments.get("requested_scopes", ["getConstraints"]),
    )
    if not auth["authorized"]:
        return json.dumps(auth, indent=2)
    data = json.loads(handle_pcl_get_constraints(user_id))
    data["app_id"] = app_id
    data["auth"] = auth
    return json.dumps(data, indent=2)


def _mcp_authorization(arguments: dict) -> str:
    api_key = str(arguments.get("developer_api_key") or arguments.get("api_key") or "").strip()
    if api_key:
        return f"Bearer {api_key}"
    return str(arguments.get("authorization") or "").strip()


def _resolve_mcp_user_id(user_id: str, user_token: str) -> str:
    token = str(user_token or "").strip()
    if token.startswith("user:"):
        return token[5:] or user_id
    return user_id


# ── MCP tool definitions ──────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_persona",
            description=(
                "Get the full persona profile of the user. "
                "Use this to understand who they are, their expertise, communication style, "
                "values, and decision-making patterns."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="get_context",
            description=(
                "Get the user's knowledge depth and interest level for a specific topic. "
                "Returns: depth (expert/learning/shallow/unknown) and related obsessions."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic to check, e.g. 'vector databases', 'Python', 'React'",
                    }
                },
                "required": ["topic"],
            },
        ),
        types.Tool(
            name="get_current_focus",
            description=(
                "Get what the user is currently working on, what's blocking them, "
                "what they're learning this week, and their active working hours."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="negotiate_context_contract",
            description=(
                "Declare a platform's facilities and receive a contract describing "
                "which persona fields PersonalLayer will share for personalization."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "platform_type": {"type": "string"},
                    "facilities": {"type": "array", "items": {"type": "string"}},
                    "requested_context": {"type": "array", "items": {"type": "string"}},
                    "purpose": {"type": "string"},
                    "retention": {"type": "string"},
                },
                "required": ["platform_type", "facilities"],
            },
        ),
        types.Tool(
            name="get_scoped_persona",
            description=(
                "Return only the persona context allowed by a previously negotiated contract. "
                "Raw browsing, email, contact, and private data are never returned."
            ),
            inputSchema={
                "type": "object",
                "properties": {"contract_id": {"type": "string"}},
                "required": ["contract_id"],
            },
        ),
        types.Tool(
            name="list_context_contracts",
            description="List recent context contracts, including active and revoked contracts.",
            inputSchema={
                "type": "object",
                "properties": {"limit": {"type": "integer"}},
            },
        ),
        types.Tool(
            name="revoke_context_contract",
            description="Revoke a context contract so future scoped persona requests are denied.",
            inputSchema={
                "type": "object",
                "properties": {"contract_id": {"type": "string"}},
                "required": ["contract_id"],
            },
        ),
        types.Tool(
            name="record_persona_feedback",
            description=(
                "Correct the living persona by confirming, boosting, rejecting, or hiding "
                "a derived signal."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "signal_type": {"type": "string"},
                    "name": {"type": "string"},
                    "action": {"type": "string", "enum": ["confirm", "reject", "hide", "boost"]},
                    "reason": {"type": "string"},
                },
                "required": ["signal_type", "name", "action"],
            },
        ),
        types.Tool(
            name="get_living_persona",
            description=(
                "Get the continuously updated local persona summary built from derived signals, "
                "including interests, skills, tools, work domains, and trends."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="predict_next_context",
            description=(
                "Predict the user's likely next task, work domain, and context fields "
                "an AI tool should preload. Uses local browser, LLM, MCP, and persona signals."
            ),
            inputSchema={
                "type": "object",
                "properties": {"days": {"type": "integer"}},
            },
        ),
        types.Tool(
            name="getProfile",
            description="Get the typed Personal Context Layer profile for the user.",
            inputSchema={
                "type": "object",
                "properties": {"user_id": {"type": "string"}},
            },
        ),
        types.Tool(
            name="getFeatureUsage",
            description="Get aggregated feature usage signals for a user, optionally scoped to one app.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "app_id": {"type": "string"},
                    "days": {"type": "integer"},
                },
            },
        ),
        types.Tool(
            name="getContext",
            description=(
                "Return a scoped, decision-ready PCL bundle for a registered app. "
                "Only app-allowed context layers are returned, and the query is logged."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "app_id": {"type": "string"},
                    "user_id": {"type": "string"},
                    "purpose": {"type": "string"},
                    "requested_layers": {"type": "array", "items": {"type": "string"}},
                    "features": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "feature_id": {"type": "string"},
                                "name": {"type": "string"},
                                "category": {"type": "string"},
                            },
                            "required": ["feature_id", "name"],
                        },
                    },
                },
                "required": ["app_id", "features"],
            },
        ),
        types.Tool(
            name="getContextBundle",
            description=(
                "Get a v1 ContextLayer bundle using intent-boundary retrieval. "
                "Returns features, suppressed features, active context, constraints, confidence, and stale status."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "app_id": {"type": "string"},
                    "intent": {"type": "string"},
                    "requested_scopes": {"type": "array", "items": {"type": "string"}},
                    "developer_api_key": {"type": "string"},
                    "user_token": {"type": "string"},
                },
                "required": ["app_id"],
            },
        ),
        types.Tool(
            name="getActiveContext",
            description="Get the current active context heartbeat for the user.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "app_id": {"type": "string"},
                    "requested_scopes": {"type": "array", "items": {"type": "string"}},
                    "developer_api_key": {"type": "string"},
                    "user_token": {"type": "string"},
                },
            },
        ),
        types.Tool(
            name="getFeatureSignals",
            description=(
                "Get v1 ContextLayer feature_signals rows, including recency_score, tier, "
                "synthetic status, and abstract attributes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "app_id": {"type": "string"},
                    "active_only": {"type": "boolean"},
                    "requested_scopes": {"type": "array", "items": {"type": "string"}},
                    "developer_api_key": {"type": "string"},
                    "user_token": {"type": "string"},
                },
            },
        ),
        types.Tool(
            name="getConstraints",
            description="Get explicit hard rules and constraints declared by or inferred for the user.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "app_id": {"type": "string"},
                    "requested_scopes": {"type": "array", "items": {"type": "string"}},
                    "developer_api_key": {"type": "string"},
                    "user_token": {"type": "string"},
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "get_persona":
        text = handle_get_persona()
    elif name == "get_context":
        topic = arguments.get("topic", "")
        text = handle_get_context(topic)
    elif name == "get_current_focus":
        text = handle_get_current_focus()
    elif name == "negotiate_context_contract":
        text = handle_negotiate_context(arguments)
    elif name == "get_scoped_persona":
        text = handle_get_scoped_persona(arguments.get("contract_id", ""))
    elif name == "list_context_contracts":
        text = handle_list_context_contracts(arguments.get("limit", 20))
    elif name == "revoke_context_contract":
        text = handle_revoke_context_contract(arguments.get("contract_id", ""))
    elif name == "record_persona_feedback":
        text = handle_record_persona_feedback(arguments)
    elif name == "get_living_persona":
        text = handle_get_living_persona()
    elif name == "predict_next_context":
        text = handle_predict_next_context(arguments.get("days", 14))
    elif name == "getProfile":
        text = handle_pcl_get_profile(arguments.get("user_id", "local_user"))
    elif name == "getFeatureUsage":
        text = handle_pcl_get_feature_usage(arguments)
    elif name == "getContext":
        text = handle_pcl_get_context(arguments)
    elif name == "getContextBundle":
        text = handle_contextlayer_get_bundle(arguments)
    elif name == "getActiveContext":
        text = handle_contextlayer_get_active_context(arguments)
    elif name == "getFeatureSignals":
        text = handle_contextlayer_get_feature_usage(arguments)
    elif name == "getConstraints":
        text = handle_contextlayer_get_constraints(arguments)
    else:
        text = json.dumps({"error": f"Unknown tool: {name}"})

    return [types.TextContent(type="text", text=text)]


# ── Entry point ───────────────────────────────────────────────────────────────

async def main() -> None:
    if stdio_server is None:
        raise RuntimeError("MCP SDK is not available in this Python environment")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
