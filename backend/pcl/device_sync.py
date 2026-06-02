from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
import uuid
from typing import Any, Optional

import database
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pcl.memory import append_memory_entry, list_memory_files, read_memory_file
from pcl.vault import decrypt_bundle, encrypt_bundle


PAIRING_TTL_SECONDS = 10 * 60
DEFAULT_PAIRING_SCOPES = ["profile_summary", "preferences", "feature_signals", "memory_summaries"]


def generate_device_keypair() -> dict:
    private_key = x25519.X25519PrivateKey.generate()
    public_key = private_key.public_key()
    return {
        "algorithm": "x25519-aesgcm-v1",
        "private_key": _b64(private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )),
        "public_key": _b64(public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )),
    }


def start_pairing_session(
    user_id: str,
    requester_device_id: str,
    requester_device_name: str = "",
    requester_public_key: str = "",
    requested_scopes: Optional[list[str]] = None,
    ttl_seconds: int = PAIRING_TTL_SECONDS,
) -> dict:
    if not requester_public_key:
        return {"status": "error", "error": "requester_public_key_required"}
    existing = database.get_sync_device(user_id, requester_device_id)
    if existing and existing.get("trust_status") == "revoked":
        return {"status": "error", "error": "device_revoked"}
    requested_scopes = requested_scopes or DEFAULT_PAIRING_SCOPES
    pairing_code = _pairing_code()
    expires_at = int(time.time()) + max(60, min(ttl_seconds, 3600))
    qr_payload = {
        "type": "personalayer.device_pairing.v1",
        "session_id": "",
        "pairing_code": pairing_code,
        "user_id": user_id,
        "requester_device_id": requester_device_id,
        "requester_device_name": requester_device_name,
        "requester_public_key": requester_public_key,
        "requested_scopes": requested_scopes,
        "expires_at": expires_at,
    }
    session = database.create_sync_pairing_session(
        user_id=user_id,
        requester_device_id=requester_device_id,
        requester_device_name=requester_device_name,
        requester_public_key=requester_public_key,
        pairing_code=pairing_code,
        qr_payload=qr_payload,
        requested_scopes=requested_scopes,
        expires_at=expires_at,
    )
    session["qr_payload"]["session_id"] = session["id"]
    database.update_sync_pairing_session(session["id"], status="pending")
    database.insert_sync_audit_log(
        user_id=user_id,
        action="pairing_started",
        device_id=requester_device_id,
        details={"session_id": session["id"], "requested_scopes": requested_scopes},
    )
    public_session = _public_pairing_session(database.get_sync_pairing_session(session_id=session["id"]) or session)
    return {"status": "pending", "session": public_session, "qr_payload": public_session["qr_payload"]}


def approve_pairing_session(
    user_id: str,
    pairing_code: str = "",
    session_id: str = "",
    approver_device_id: str = "",
    approver_device_name: str = "",
    approver_public_key: str = "",
) -> dict:
    session = database.get_sync_pairing_session(session_id=session_id, pairing_code=pairing_code)
    if not session:
        return {"status": "error", "error": "pairing_not_found"}
    if session["user_id"] != user_id:
        return {"status": "error", "error": "user_mismatch"}
    if _is_pairing_expired(session):
        expired = database.update_sync_pairing_session(session["id"], status="expired")
        return {"status": "expired", "session": _public_pairing_session(expired)}
    if session["status"] != "pending":
        return {"status": "error", "error": f"pairing_{session['status']}"}
    if not approver_device_id:
        return {"status": "error", "error": "approver_device_id_required"}

    requester_device_id = session["requester_device_id"]
    database.register_sync_device(
        user_id=user_id,
        device_id=requester_device_id,
        device_name=session.get("requester_device_name", ""),
        public_key=session["requester_public_key"],
        trust_status="trusted",
    )
    database.register_sync_device(
        user_id=user_id,
        device_id=approver_device_id,
        device_name=approver_device_name,
        public_key=approver_public_key,
        trust_status="trusted",
    )
    snapshot = create_sync_snapshot(
        user_id=user_id,
        device_id=approver_device_id,
        device_name=approver_device_name,
        public_key=approver_public_key,
    )
    if snapshot.get("status") != "created":
        return snapshot
    summary_payload = decrypt_summary_blob(snapshot["encrypted_blob"])
    transfer_envelope = encrypt_transfer_payload(summary_payload, session["requester_public_key"])
    recovery_token = secrets.token_urlsafe(24)
    updated = database.update_sync_pairing_session(
        session["id"],
        status="approved",
        approver_device_id=approver_device_id,
        approver_public_key=approver_public_key,
        transfer_envelope=json.dumps(transfer_envelope, sort_keys=True),
        recovery_token_hash=_hash_recovery_token(recovery_token),
        approved_at=str(int(time.time())),
    )
    database.insert_sync_audit_log(
        user_id=user_id,
        action="pairing_approved",
        device_id=requester_device_id,
        version=summary_payload["version"],
        details={"session_id": session["id"], "approver_device_id": approver_device_id},
    )
    public_session = _public_pairing_session(updated)
    return {
        "status": "approved",
        "session": public_session,
        "transfer_envelope": transfer_envelope,
        "recovery_token": recovery_token,
    }


def get_pairing_session(user_id: str, session_id: str = "", pairing_code: str = "") -> dict:
    session = database.get_sync_pairing_session(session_id=session_id, pairing_code=pairing_code)
    if not session or session["user_id"] != user_id:
        return {"status": "error", "error": "pairing_not_found"}
    if session["status"] == "pending" and _is_pairing_expired(session):
        session = database.update_sync_pairing_session(session["id"], status="expired")
    return {"status": session["status"], "session": _public_pairing_session(session)}


def claim_pairing_transfer(
    user_id: str,
    session_id: str,
    requester_device_id: str,
    requester_private_key: str = "",
) -> dict:
    session = database.get_sync_pairing_session(session_id=session_id)
    if not session or session["user_id"] != user_id:
        return {"status": "error", "error": "pairing_not_found"}
    if session["requester_device_id"] != requester_device_id:
        return {"status": "error", "error": "device_mismatch"}
    if session["status"] not in {"approved", "claimed"}:
        return {"status": "error", "error": f"pairing_{session['status']}"}
    if not session.get("transfer_envelope"):
        return {"status": "error", "error": "transfer_not_ready"}

    transfer_envelope = json.loads(session["transfer_envelope"])
    if not requester_private_key:
        return {
            "status": "ready",
            "session": _public_pairing_session(session),
            "transfer_envelope": transfer_envelope,
        }

    payload = decrypt_transfer_payload(transfer_envelope, requester_private_key)
    merged = merge_summary_payload(user_id, payload, source=f"sync:{payload.get('device_id', 'mobile')}:pairing")
    local_snapshot = create_sync_snapshot(user_id=user_id, device_id=requester_device_id)
    updated = database.update_sync_pairing_session(
        session_id,
        status="claimed",
        claimed_at=str(int(time.time())),
    )
    database.insert_sync_audit_log(
        user_id=user_id,
        action="pairing_claimed",
        device_id=requester_device_id,
        version=payload.get("version", ""),
        details={"session_id": session_id, "merged": merged},
    )
    return {
        "status": "claimed",
        "session": _public_pairing_session(updated),
        "merged": merged,
        "local_snapshot": local_snapshot.get("snapshot"),
    }


def rotate_sync_device_key(
    user_id: str,
    device_id: str,
    public_key: str,
    recovery_token: str = "",
) -> dict:
    existing = database.get_sync_device(user_id, device_id)
    if not existing:
        return {"status": "error", "error": "device_not_found"}
    if existing.get("trust_status") == "revoked":
        return {"status": "error", "error": "device_revoked"}
    device = database.register_sync_device(
        user_id=user_id,
        device_id=device_id,
        device_name=existing.get("device_name", ""),
        public_key=public_key,
        trust_status="trusted",
    )
    database.insert_sync_audit_log(
        user_id=user_id,
        action="device_key_rotated",
        device_id=device_id,
        details={"recovery_token_present": bool(recovery_token)},
    )
    return {"status": "rotated", "device": device}


def revoke_sync_device_with_recovery(user_id: str, device_id: str, reason: str = "") -> dict:
    result = revoke_sync_device(user_id, device_id)
    if result.get("status") != "revoked":
        return result
    database.insert_sync_audit_log(
        user_id=user_id,
        action="device_recovery_revocation",
        device_id=device_id,
        details={"reason": reason, "rule": "revoked devices cannot create or import snapshots"},
    )
    return result


def encrypt_transfer_payload(payload: dict[str, Any], recipient_public_key: str) -> dict:
    ephemeral_private = x25519.X25519PrivateKey.generate()
    recipient_public = x25519.X25519PublicKey.from_public_bytes(_unb64(recipient_public_key))
    shared = ephemeral_private.exchange(recipient_public)
    key = hashlib.sha256(shared + b"personalayer-sync-transfer-v1").digest()
    nonce = secrets.token_bytes(12)
    plaintext = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
    return {
        "schema": "personalayer.transfer.x25519-aesgcm.v1",
        "ephemeral_public_key": _b64(ephemeral_private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )),
        "nonce": _b64(nonce),
        "ciphertext": _b64(ciphertext),
    }


def decrypt_transfer_payload(envelope: dict[str, str], recipient_private_key: str) -> dict:
    if envelope.get("schema") != "personalayer.transfer.x25519-aesgcm.v1":
        raise ValueError("unsupported_transfer_envelope")
    private_key = x25519.X25519PrivateKey.from_private_bytes(_unb64(recipient_private_key))
    ephemeral_public = x25519.X25519PublicKey.from_public_bytes(_unb64(envelope["ephemeral_public_key"]))
    shared = private_key.exchange(ephemeral_public)
    key = hashlib.sha256(shared + b"personalayer-sync-transfer-v1").digest()
    plaintext = AESGCM(key).decrypt(_unb64(envelope["nonce"]), _unb64(envelope["ciphertext"]), None)
    return json.loads(plaintext.decode("utf-8"))


def create_sync_snapshot(
    user_id: str,
    device_id: str,
    device_name: str = "",
    public_key: str = "",
) -> dict:
    existing_device = database.get_sync_device(user_id, device_id)
    if existing_device and existing_device.get("trust_status") == "revoked":
        return {"status": "error", "error": "device_revoked"}
    database.register_sync_device(
        user_id=user_id,
        device_id=device_id,
        device_name=device_name,
        public_key=public_key,
        trust_status="trusted",
    )
    latest = database.latest_encrypted_summary_blob(user_id=user_id, device_id=device_id)
    parent_version = latest["version"] if latest else ""
    payload = build_summary_payload(user_id, device_id, parent_version)
    plaintext = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    encrypted = encrypt_bundle(plaintext)
    encrypted_blob = json.dumps(encrypted, sort_keys=True)
    saved = database.save_encrypted_summary_blob(
        user_id=user_id,
        device_id=device_id,
        version=payload["version"],
        parent_version=parent_version,
        summary_hash=payload["summary_hash"],
        encrypted_blob=encrypted_blob,
        merge_status="local",
    )
    database.insert_sync_audit_log(
        user_id=user_id,
        action="snapshot_created",
        device_id=device_id,
        version=payload["version"],
        details={"parent_version": parent_version, "summary_hash": payload["summary_hash"]},
    )
    return {
        "status": "created",
        "snapshot": _public_blob(saved),
        "encrypted_blob": encrypted_blob,
    }


def build_summary_payload(user_id: str, device_id: str, parent_version: str = "") -> dict:
    files = {}
    for item in list_memory_files(user_id):
        memory = read_memory_file(user_id, item["scope"])
        files[item["scope"]] = {
            "content": memory["content"],
            "updated_at": memory["updated_at"],
        }
    canonical = json.dumps(files, sort_keys=True, separators=(",", ":"))
    summary_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    version = hashlib.sha256(f"{device_id}:{parent_version}:{summary_hash}".encode("utf-8")).hexdigest()
    return {
        "schema": "personalayer.summary.v1",
        "user_id": user_id,
        "device_id": device_id,
        "parent_version": parent_version,
        "version": version,
        "summary_hash": summary_hash,
        "memory": files,
    }


def import_sync_snapshot(
    user_id: str,
    remote_device_id: str,
    encrypted_blob: str,
    expected_parent_version: Optional[str] = None,
) -> dict:
    remote_device = database.get_sync_device(user_id, remote_device_id)
    if remote_device and remote_device.get("trust_status") == "revoked":
        return {"status": "error", "error": "device_revoked"}
    if remote_device and remote_device.get("trust_status") == "pending":
        return {"status": "error", "error": "device_not_trusted"}
    payload = decrypt_summary_blob(encrypted_blob)
    if payload.get("user_id") != user_id:
        return {"status": "error", "error": "user_mismatch"}
    remote_version = payload["version"]
    parent_version = payload.get("parent_version", "")
    latest_local = database.latest_encrypted_summary_blob(user_id=user_id)
    local_version = latest_local["version"] if latest_local else ""
    explicit_parent_check = expected_parent_version is not None
    expected_parent_version = expected_parent_version if explicit_parent_check else local_version
    if explicit_parent_check and parent_version != expected_parent_version:
        merge_status = "conflict"
    else:
        merge_status = "merged" if parent_version in {"", expected_parent_version, local_version} else "conflict"

    saved = database.save_encrypted_summary_blob(
        user_id=user_id,
        device_id=remote_device_id,
        version=remote_version,
        parent_version=parent_version,
        summary_hash=payload["summary_hash"],
        encrypted_blob=encrypted_blob,
        merge_status=merge_status,
    )
    if merge_status == "conflict":
        conflict = database.create_sync_conflict(
            user_id=user_id,
            local_version=local_version,
            remote_version=remote_version,
            reason="parent_version_diverged",
            details={
                "remote_device_id": remote_device_id,
                "remote_parent_version": parent_version,
                "expected_parent_version": expected_parent_version,
            },
        )
        return {"status": "conflict", "snapshot": _public_blob(saved), "conflict": conflict}

    merged = merge_summary_payload(user_id, payload, source=f"sync:{remote_device_id}")
    database.insert_sync_audit_log(
        user_id=user_id,
        action="snapshot_imported",
        device_id=remote_device_id,
        version=remote_version,
        details={"merge_status": "merged", "merged": merged},
    )
    return {"status": "merged", "snapshot": _public_blob(saved), "merged": merged}


def merge_summary_payload(user_id: str, payload: dict[str, Any], source: str) -> dict:
    updates = []
    for scope, item in (payload.get("memory") or {}).items():
        content = str(item.get("content") or "")
        for line in content.splitlines():
            clean = line.strip()
            if not clean or clean.startswith("#") or _is_placeholder_memory(clean):
                continue
            updates.append(append_memory_entry(
                user_id=user_id,
                scope=scope,
                entry=clean,
                heading=f"Synced from {payload.get('device_id', 'device')}: {_short_heading(clean)}",
                source=source,
                reason="cross-device summary merge",
            ))
    return {"updated": len(updates), "scopes": sorted({item["scope"] for item in updates})}


def decrypt_summary_blob(encrypted_blob: str) -> dict:
    envelope = json.loads(encrypted_blob)
    plaintext = decrypt_bundle(envelope)
    return json.loads(plaintext.decode("utf-8"))


def list_sync_state(user_id: str) -> dict:
    return {
        "user_id": user_id,
        "devices": database.list_sync_devices(user_id),
        "snapshots": database.list_encrypted_summary_blobs(user_id),
        "conflicts": database.list_sync_conflicts(user_id, status="open"),
        "audit": database.list_sync_audit_logs(user_id, limit=25),
    }


def compact_sync_snapshots(user_id: str, keep_per_device: int = 5) -> dict:
    return database.compact_encrypted_summary_blobs(user_id, keep_per_device=keep_per_device)


def register_pending_sync_device(
    user_id: str,
    device_id: str,
    device_name: str = "",
    public_key: str = "",
) -> dict:
    existing = database.get_sync_device(user_id, device_id)
    if existing and existing.get("trust_status") == "revoked":
        return {"status": "error", "error": "device_revoked"}
    device = database.register_sync_device(
        user_id=user_id,
        device_id=device_id,
        device_name=device_name,
        public_key=public_key,
        trust_status="pending",
    )
    database.insert_sync_audit_log(
        user_id=user_id,
        action="device_pending",
        device_id=device_id,
        details={"device_name": device_name},
    )
    return {"status": "pending", "device": device}


def trust_sync_device(
    user_id: str,
    device_id: str,
    device_name: str = "",
    public_key: str = "",
) -> dict:
    existing = database.get_sync_device(user_id, device_id)
    if not existing:
        return {"status": "error", "error": "device_not_found"}
    device = database.register_sync_device(
        user_id=user_id,
        device_id=device_id,
        device_name=device_name or existing.get("device_name", ""),
        public_key=public_key or existing.get("public_key", ""),
        trust_status="trusted",
    )
    database.insert_sync_audit_log(
        user_id=user_id,
        action="device_trusted",
        device_id=device_id,
        details={"device_name": device.get("device_name", "")},
    )
    return {"status": "trusted", "device": device}


def revoke_sync_device(user_id: str, device_id: str) -> dict:
    existing = database.get_sync_device(user_id, device_id)
    if not existing:
        return {"status": "error", "error": "device_not_found"}
    device = database.register_sync_device(
        user_id=user_id,
        device_id=device_id,
        device_name=existing.get("device_name", ""),
        public_key=existing.get("public_key", ""),
        trust_status="revoked",
    )
    database.insert_sync_audit_log(
        user_id=user_id,
        action="device_revoked",
        device_id=device_id,
    )
    return {"status": "revoked", "device": device}


def resolve_sync_conflict(
    user_id: str,
    conflict_id: str,
    action: str,
    device_id: str = "",
) -> dict:
    conflict = database.get_sync_conflict(conflict_id)
    if not conflict or conflict.get("user_id") != user_id:
        return {"status": "error", "error": "conflict_not_found"}
    if conflict.get("status") != "open":
        return {"status": "error", "error": "conflict_not_open", "conflict": conflict}
    if action not in {"accept_remote", "keep_local", "ignore"}:
        return {"status": "error", "error": "invalid_conflict_action"}

    if action == "ignore":
        resolved = database.resolve_sync_conflict(
            conflict_id,
            status="ignored",
            details={"resolution": "ignore", "resolved_by_device_id": device_id},
        )
        return {"status": "ignored", "conflict": resolved}

    remote_version = conflict.get("remote_version", "")
    if action == "keep_local":
        database.update_encrypted_summary_blob_status(user_id, remote_version, "conflict")
        resolved = database.resolve_sync_conflict(
            conflict_id,
            status="resolved",
            details={"resolution": "keep_local", "resolved_by_device_id": device_id},
        )
        return {"status": "resolved", "resolution": "keep_local", "conflict": resolved}

    remote_blob = database.get_encrypted_summary_blob_by_version(user_id, remote_version)
    if not remote_blob:
        return {"status": "error", "error": "remote_snapshot_not_found"}
    payload = decrypt_summary_blob(remote_blob["encrypted_blob"])
    merged = merge_summary_payload(
        user_id=user_id,
        payload=payload,
        source=f"sync:{payload.get('device_id', 'remote')}:conflict-resolution",
    )
    database.update_encrypted_summary_blob_status(user_id, remote_version, "merged")
    if device_id:
        create_sync_snapshot(user_id=user_id, device_id=device_id)
    resolved = database.resolve_sync_conflict(
        conflict_id,
        status="resolved",
        details={
            "resolution": "accept_remote",
            "resolved_by_device_id": device_id,
            "merged": merged,
        },
    )
    return {
        "status": "resolved",
        "resolution": "accept_remote",
        "merged": merged,
        "conflict": resolved,
    }


def _public_blob(blob: dict) -> dict:
    return {key: value for key, value in blob.items() if key != "encrypted_blob"}


def _public_pairing_session(session: Optional[dict]) -> dict:
    if not session:
        return {}
    public = dict(session)
    public.pop("transfer_envelope", None)
    public.pop("recovery_token_hash", None)
    return public


def _is_pairing_expired(session: dict) -> bool:
    return int(session.get("expires_at") or 0) < int(time.time())


def _pairing_code() -> str:
    digits = "".join(str(secrets.randbelow(10)) for _ in range(8))
    return f"{digits[:4]}-{digits[4:]}"


def _hash_recovery_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _short_heading(value: str) -> str:
    return " ".join(value.split())[:72] or str(uuid.uuid4())[:8]


def _is_placeholder_memory(value: str) -> bool:
    return value.lower().rstrip(".") == "no confirmed memory yet"
