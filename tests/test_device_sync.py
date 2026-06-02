import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


def test_device_sync_snapshot_encrypts_memory_and_registers_device(monkeypatch, tmp_path):
    import database
    from pcl.device_sync import create_sync_snapshot, decrypt_summary_blob
    from pcl.memory import write_memory_file

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'device_sync.db')
    database.create_tables()
    write_memory_file("user_1", "projects", "# Projects\n\nBuilding PersonaLayer.\n")

    snapshot = create_sync_snapshot("user_1", "laptop", device_name="Laptop")
    state = database.list_encrypted_summary_blobs("user_1")
    payload = decrypt_summary_blob(snapshot["encrypted_blob"])

    assert snapshot["status"] == "created"
    assert database.get_sync_device("user_1", "laptop")["device_name"] == "Laptop"
    assert state[0]["version"] == snapshot["snapshot"]["version"]
    assert "Building PersonaLayer" not in snapshot["encrypted_blob"]
    assert payload["memory"]["projects"]["content"].endswith("Building PersonaLayer.\n")


def test_device_sync_import_merges_remote_memory(monkeypatch, tmp_path):
    import database
    from pcl.device_sync import create_sync_snapshot, import_sync_snapshot
    from pcl.memory import read_memory_file, write_memory_file

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'device_sync_merge.db')
    database.create_tables()
    write_memory_file("user_1", "people", "# People\n\nAlex is a collaborator.\n")
    remote = create_sync_snapshot("user_1", "phone")

    result = import_sync_snapshot(
        user_id="user_1",
        remote_device_id="phone",
        encrypted_blob=remote["encrypted_blob"],
        expected_parent_version="",
    )

    assert result["status"] == "merged"
    assert "Alex is a collaborator." in read_memory_file("user_1", "people")["content"]


def test_device_sync_import_records_conflict_on_diverged_parent(monkeypatch, tmp_path):
    import database
    from pcl.device_sync import create_sync_snapshot, import_sync_snapshot
    from pcl.memory import write_memory_file

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'device_sync_conflict.db')
    database.create_tables()
    write_memory_file("user_1", "projects", "# Projects\n\nPhone version.\n")
    remote = create_sync_snapshot("user_1", "phone")
    write_memory_file("user_1", "projects", "# Projects\n\nLaptop version.\n")
    create_sync_snapshot("user_1", "laptop")

    result = import_sync_snapshot(
        user_id="user_1",
        remote_device_id="phone",
        encrypted_blob=remote["encrypted_blob"],
        expected_parent_version="different-parent",
    )
    conflicts = database.list_sync_conflicts("user_1")

    assert result["status"] == "conflict"
    assert conflicts[0]["reason"] == "parent_version_diverged"
    assert conflicts[0]["remote_version"] == remote["snapshot"]["version"]


def test_device_sync_conflict_accept_remote_merges_and_resolves(monkeypatch, tmp_path):
    import database
    from pcl.device_sync import create_sync_snapshot, import_sync_snapshot, resolve_sync_conflict
    from pcl.memory import read_memory_file, write_memory_file

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'device_sync_accept_conflict.db')
    database.create_tables()
    write_memory_file("user_1", "projects", "# Projects\n\nPhone version.\n")
    remote = create_sync_snapshot("user_1", "phone")
    write_memory_file("user_1", "projects", "# Projects\n\nLaptop version.\n")
    create_sync_snapshot("user_1", "laptop")

    result = import_sync_snapshot(
        user_id="user_1",
        remote_device_id="phone",
        encrypted_blob=remote["encrypted_blob"],
        expected_parent_version="different-parent",
    )
    conflict_id = result["conflict"]["id"]
    resolved = resolve_sync_conflict(
        user_id="user_1",
        conflict_id=conflict_id,
        action="accept_remote",
        device_id="laptop",
    )

    assert resolved["status"] == "resolved"
    assert resolved["resolution"] == "accept_remote"
    assert database.get_sync_conflict(conflict_id)["status"] == "resolved"
    assert "Phone version." in read_memory_file("user_1", "projects")["content"]


def test_device_sync_conflict_keep_local_resolves_without_merge(monkeypatch, tmp_path):
    import database
    from pcl.device_sync import create_sync_snapshot, import_sync_snapshot, resolve_sync_conflict
    from pcl.memory import read_memory_file, write_memory_file

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'device_sync_keep_local.db')
    database.create_tables()
    write_memory_file("user_1", "projects", "# Projects\n\nPhone version.\n")
    remote = create_sync_snapshot("user_1", "phone")
    write_memory_file("user_1", "projects", "# Projects\n\nLaptop version.\n")
    create_sync_snapshot("user_1", "laptop")

    result = import_sync_snapshot(
        user_id="user_1",
        remote_device_id="phone",
        encrypted_blob=remote["encrypted_blob"],
        expected_parent_version="different-parent",
    )
    conflict_id = result["conflict"]["id"]
    resolved = resolve_sync_conflict(
        user_id="user_1",
        conflict_id=conflict_id,
        action="keep_local",
        device_id="laptop",
    )

    content = read_memory_file("user_1", "projects")["content"]
    assert resolved["status"] == "resolved"
    assert resolved["resolution"] == "keep_local"
    assert database.get_sync_conflict(conflict_id)["status"] == "resolved"
    assert content.count("Phone version.") == 0
    assert "Laptop version." in content


def test_device_sync_trust_and_revoke_blocks_sync(monkeypatch, tmp_path):
    import database
    from pcl.device_sync import (
        create_sync_snapshot,
        register_pending_sync_device,
        revoke_sync_device,
        trust_sync_device,
    )
    from pcl.memory import write_memory_file

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'device_sync_trust.db')
    database.create_tables()
    write_memory_file("user_1", "projects", "# Projects\n\nTrusted sync.\n")

    pending = register_pending_sync_device("user_1", "phone", device_name="Phone", public_key="pub")
    trusted = trust_sync_device("user_1", "phone")
    snapshot = create_sync_snapshot("user_1", "phone")
    revoked = revoke_sync_device("user_1", "phone")
    blocked = create_sync_snapshot("user_1", "phone")

    assert pending["status"] == "pending"
    assert trusted["status"] == "trusted"
    assert snapshot["status"] == "created"
    assert revoked["status"] == "revoked"
    assert blocked == {"status": "error", "error": "device_revoked"}


def test_device_sync_compacts_snapshots_and_records_audit(monkeypatch, tmp_path):
    import database
    from pcl.device_sync import compact_sync_snapshots, create_sync_snapshot
    from pcl.memory import write_memory_file

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'device_sync_compact.db')
    database.create_tables()
    write_memory_file("user_1", "projects", "# Projects\n\nInitial.\n")
    for index in range(4):
        write_memory_file("user_1", "projects", f"# Projects\n\nUpdate {index}.\n")
        create_sync_snapshot("user_1", "laptop")

    compacted = compact_sync_snapshots("user_1", keep_per_device=2)
    snapshots = database.list_encrypted_summary_blobs("user_1", limit=10)
    audit = database.list_sync_audit_logs("user_1", limit=20)

    assert compacted["deleted"] >= 1
    assert len(snapshots) == 2
    assert any(item["action"] == "summary_blobs_compacted" for item in audit)
    assert any(item["action"] == "snapshot_created" for item in audit)


def test_device_sync_conflict_missing_remote_blob_stays_open(monkeypatch, tmp_path):
    import database
    from pcl.device_sync import resolve_sync_conflict

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'device_sync_missing_remote.db')
    database.create_tables()
    conflict = database.create_sync_conflict(
        user_id="user_1",
        local_version="local-version",
        remote_version="missing-version",
        reason="parent_version_diverged",
    )

    result = resolve_sync_conflict(
        user_id="user_1",
        conflict_id=conflict["id"],
        action="accept_remote",
        device_id="laptop",
    )

    assert result == {"status": "error", "error": "remote_snapshot_not_found"}
    assert database.get_sync_conflict(conflict["id"])["status"] == "open"


def test_device_sync_already_resolved_conflict_cannot_resolve_again(monkeypatch, tmp_path):
    import database
    from pcl.device_sync import resolve_sync_conflict

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'device_sync_already_resolved.db')
    database.create_tables()
    conflict = database.create_sync_conflict(
        user_id="user_1",
        local_version="local-version",
        remote_version="remote-version",
        reason="parent_version_diverged",
    )
    first = resolve_sync_conflict(
        user_id="user_1",
        conflict_id=conflict["id"],
        action="keep_local",
        device_id="laptop",
    )
    second = resolve_sync_conflict(
        user_id="user_1",
        conflict_id=conflict["id"],
        action="ignore",
        device_id="laptop",
    )

    assert first["status"] == "resolved"
    assert second["status"] == "error"
    assert second["error"] == "conflict_not_open"


def test_device_sync_lists_multiple_open_conflicts(monkeypatch, tmp_path):
    import database
    from pcl.device_sync import list_sync_state

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'device_sync_multiple_conflicts.db')
    database.create_tables()
    database.create_sync_conflict("user_1", "local-a", "remote-a", "parent_version_diverged")
    database.create_sync_conflict("user_1", "local-b", "remote-b", "parent_version_diverged")

    state = list_sync_state("user_1")

    assert len(state["conflicts"]) == 2
    assert {item["remote_version"] for item in state["conflicts"]} == {"remote-a", "remote-b"}


def test_device_pairing_qr_approval_and_claim_merges_mobile_memory(monkeypatch, tmp_path):
    import database
    from pcl.device_sync import (
        approve_pairing_session,
        claim_pairing_transfer,
        generate_device_keypair,
        start_pairing_session,
    )
    from pcl.memory import read_memory_file, write_memory_file

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'device_pairing.db')
    database.create_tables()
    write_memory_file("user_1", "projects", "# Projects\n\nMobile onboarding completed.\n")

    laptop_keys = generate_device_keypair()
    phone_keys = generate_device_keypair()
    started = start_pairing_session(
        user_id="user_1",
        requester_device_id="laptop",
        requester_device_name="Laptop",
        requester_public_key=laptop_keys["public_key"],
    )
    session_id = started["session"]["id"]
    assert started["status"] == "pending"
    assert started["qr_payload"]["type"] == "personalayer.device_pairing.v1"
    assert started["qr_payload"]["requester_public_key"] == laptop_keys["public_key"]

    approved = approve_pairing_session(
        user_id="user_1",
        pairing_code=started["session"]["pairing_code"],
        approver_device_id="phone",
        approver_device_name="Phone",
        approver_public_key=phone_keys["public_key"],
    )
    assert approved["status"] == "approved"
    assert "ciphertext" in approved["transfer_envelope"]
    assert database.get_sync_device("user_1", "laptop")["trust_status"] == "trusted"
    assert database.get_sync_device("user_1", "phone")["trust_status"] == "trusted"

    write_memory_file("user_1", "projects", "# Projects\n\n")
    claimed = claim_pairing_transfer(
        user_id="user_1",
        session_id=session_id,
        requester_device_id="laptop",
        requester_private_key=laptop_keys["private_key"],
    )
    assert claimed["status"] == "claimed"
    assert claimed["merged"]["updated"] >= 1
    assert "Mobile onboarding completed." in read_memory_file("user_1", "projects")["content"]


def test_device_pairing_can_poll_transfer_without_private_key(monkeypatch, tmp_path):
    import database
    from pcl.device_sync import (
        approve_pairing_session,
        claim_pairing_transfer,
        generate_device_keypair,
        start_pairing_session,
    )
    from pcl.memory import write_memory_file

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'device_pairing_poll.db')
    database.create_tables()
    write_memory_file("user_1", "preferences", "# Preferences\n\nPrefers concise summaries.\n")

    laptop_keys = generate_device_keypair()
    started = start_pairing_session("user_1", "laptop", requester_public_key=laptop_keys["public_key"])
    approve_pairing_session(
        user_id="user_1",
        session_id=started["session"]["id"],
        approver_device_id="phone",
    )

    ready = claim_pairing_transfer("user_1", started["session"]["id"], "laptop")

    assert ready["status"] == "ready"
    assert ready["transfer_envelope"]["schema"] == "personalayer.transfer.x25519-aesgcm.v1"
    assert "ciphertext" in ready["transfer_envelope"]


def test_device_key_rotation_and_recovery_revoke(monkeypatch, tmp_path):
    import database
    from pcl.device_sync import (
        create_sync_snapshot,
        generate_device_keypair,
        revoke_sync_device_with_recovery,
        rotate_sync_device_key,
    )

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'device_key_lifecycle.db')
    database.create_tables()

    first_keys = generate_device_keypair()
    second_keys = generate_device_keypair()
    create_sync_snapshot("user_1", "laptop", public_key=first_keys["public_key"])
    rotated = rotate_sync_device_key("user_1", "laptop", second_keys["public_key"], recovery_token="token")
    revoked = revoke_sync_device_with_recovery("user_1", "laptop", reason="lost device")
    blocked = create_sync_snapshot("user_1", "laptop")

    assert rotated["status"] == "rotated"
    assert rotated["device"]["public_key"] == second_keys["public_key"]
    assert revoked["status"] == "revoked"
    assert blocked == {"status": "error", "error": "device_revoked"}
