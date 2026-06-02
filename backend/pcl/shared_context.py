import base64
import hashlib
import hmac
import json
import secrets
from pathlib import Path
from typing import Any

import database
from pcl.privacy import egress_filter
from pcl.vault import encrypt_bundle, decrypt_bundle


def write_shared_context_bundle(user_id: str) -> dict:
    bundle = build_shared_context_bundle(user_id)
    plaintext = json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode("utf-8")
    envelope = encrypt_bundle(plaintext)
    path = shared_context_bundle_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(envelope, sort_keys=True), encoding="utf-8")
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "features": len(bundle["features"]),
        "nodes": len(bundle["knowledge_graph"]["nodes"]),
        "algorithm": envelope.get("algorithm", "aes-256-gcm"),
    }


def read_shared_context_bundle(user_id: str) -> dict:
    envelope = json.loads(shared_context_bundle_path(user_id).read_text(encoding="utf-8"))
    # Legacy migration
    if envelope.get("algorithm") == "local-reference-xor-hmac-sha256":
        return _read_legacy_shared_context_bundle(user_id, envelope)
    plaintext = decrypt_bundle(envelope)
    return json.loads(plaintext.decode("utf-8"))


def build_shared_context_bundle(user_id: str) -> dict:
    profile = database.get_user_profile_record(user_id) or {}
    active_context = database.get_active_context(user_id)
    features = [
        {
            "app_id": signal["app_id"],
            "feature_id": signal["feature_id"],
            "tier": signal["tier"],
            "recency_score": signal["recency_score"],
            "decay_score": signal["decay_score"],
            "usage_count": signal["usage_count"],
        }
        for signal in database.list_feature_signals(user_id=user_id)[:20]
    ]
    nodes = [
        {
            "type": node["type"],
            "label": node["label"],
            "tier": node["tier"],
            "decay_score": node["decay_score"],
            "access_count": node["access_count"],
            "last_seen": node["last_seen"],
        }
        for node in database.list_kg_nodes(user_id=user_id, limit=30)
        if node["tier"] in {"hot", "warm"}
    ]
    return egress_filter({
        "user_id": user_id,
        "generated_at": _now_ms(),
        "features": features,
        "active_context": active_context,
        "abstract_attributes": profile.get("abstract_attributes", [])[:12],
        "context_brief": profile.get("context_brief", ""),
        "daily_insight": profile.get("daily_insight", ""),
        "knowledge_graph": {"nodes": nodes},
        "embedding_model": {
            "name": "all-MiniLM-L6-v2",
            "dimension": 384,
            "target": "all-MiniLM-L6-v2 Core ML on-device",
        },
        "privacy": {
            "filter_applied": "egress",
            "raw_events_included": False,
            "raw_payload_included": False,
            "temporal_chains_included": False,
            "cloud_sync": False,
        },
    })


def shared_context_bundle_path(user_id: str) -> Path:
    safe_user_id = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in user_id)
    return database.DATA_DIR / "shared" / f"bundle_{safe_user_id}.json"


def _device_key() -> bytes:
    path = database.DATA_DIR / "device.key"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return base64.b64decode(path.read_text(encoding="utf-8"))
    key = secrets.token_bytes(32)
    path.write_text(base64.b64encode(key).decode("ascii"), encoding="utf-8")
    return key


def _xor_stream(data: bytes, key: bytes, nonce: bytes) -> bytes:
    output = bytearray()
    counter = 0
    while len(output) < len(data):
        block = hashlib.sha256(key + nonce + counter.to_bytes(8, "big")).digest()
        output.extend(block)
        counter += 1
    return bytes(item ^ mask for item, mask in zip(data, output))


def _read_legacy_shared_context_bundle(user_id: str, envelope: dict) -> dict:
    """Migrate legacy XOR bundle to new format on read."""
    key = _device_key()
    nonce = base64.b64decode(envelope["nonce"])
    ciphertext = base64.b64decode(envelope["ciphertext"])
    expected = hmac.new(key, nonce + ciphertext, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, envelope["tag"]):
        raise ValueError("shared_context_bundle_tampered")
    plaintext = _xor_stream(ciphertext, key, nonce)
    bundle = json.loads(plaintext.decode("utf-8"))
    # Rewrite in new format
    write_shared_context_bundle(user_id)
    return bundle


def _now_ms() -> int:
    from datetime import datetime
    return int(datetime.now().timestamp() * 1000)
