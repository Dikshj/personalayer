import os
import hashlib
from datetime import datetime, timedelta
from urllib.parse import urlencode

from database import (
    connect_pcl_integration,
    consume_pcl_integration_oauth_state,
    create_pcl_integration_oauth_state,
    store_pcl_integration_oauth_token,
)
from pcl.integrations import default_integration


def start_oauth_flow(
    source: str,
    user_id: str = "local_user",
    redirect_uri: str = "",
) -> dict:
    try:
        integration = default_integration(source)
    except ValueError:
        return {"status": "error", "error": "unknown_integration"}

    oauth = integration.get("oauth")
    if not oauth:
        return {"status": "error", "error": "oauth_not_supported"}

    client_id = os.getenv(oauth["client_id_env"], "").strip()
    state = create_pcl_integration_oauth_state(
        source=source,
        user_id=user_id,
        redirect_uri=redirect_uri,
    )
    if not client_id:
        return {
            "status": "configuration_required",
            "error": "missing_oauth_client_id",
            "client_id_env": oauth["client_id_env"],
            "state": state["state"],
            "source": source,
            "redirect_uri": redirect_uri,
        }

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": state["state"],
        "access_type": "offline",
        "prompt": "consent",
    }
    if oauth.get("scopes"):
        params["scope"] = " ".join(oauth["scopes"])
    return {
        "status": "ok",
        "source": source,
        "state": state["state"],
        "auth_url": f"{oauth['authorize_url']}?{urlencode(params)}",
        "client_id_env": oauth["client_id_env"],
    }


def complete_oauth_flow(
    state: str,
    code: str,
    account_hint: str = "",
    token_response: dict | None = None,
) -> dict:
    oauth_state = consume_pcl_integration_oauth_state(state)
    if not oauth_state:
        return {"status": "error", "error": "invalid_or_consumed_state"}
    if not code.strip():
        return {"status": "error", "error": "missing_authorization_code"}

    integration = default_integration(oauth_state["source"])
    token_payload = token_response or _local_reference_token_payload(
        source=integration["source"],
        user_id=oauth_state["user_id"],
        code=code,
    )
    expires_at = token_payload.get("expires_at") or int(
        (datetime.now() + timedelta(hours=1)).timestamp() * 1000
    )
    token = store_pcl_integration_oauth_token(
        source=integration["source"],
        user_id=oauth_state["user_id"],
        token_payload=token_payload,
        account_hint=account_hint,
        scopes=integration["scopes"],
        expires_at=expires_at,
    )
    connected = connect_pcl_integration(
        source=integration["source"],
        name=integration["name"],
        scopes=integration["scopes"],
        metadata={"user_id": oauth_state["user_id"]},
        account_hint=account_hint,
        auth_status="oauth_connected_local_token_store",
        auth_expires_at=expires_at,
    )
    return {
        "status": "connected",
        "source": integration["source"],
        "user_id": oauth_state["user_id"],
        "token": token,
        "integration": connected,
    }


def _local_reference_token_payload(source: str, user_id: str, code: str) -> dict:
    digest = hashlib.sha256(f"{source}:{user_id}:{code}".encode("utf-8")).hexdigest()
    expires_at = int((datetime.now() + timedelta(hours=1)).timestamp() * 1000)
    return {
        "access_token": f"local_access_{digest}",
        "refresh_token": f"local_refresh_{digest[-32:]}",
        "token_type": "Bearer",
        "expires_at": expires_at,
        "exchange_mode": "local_reference_no_provider_network",
    }
