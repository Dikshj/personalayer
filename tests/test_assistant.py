import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


@pytest.fixture(autouse=True)
def use_test_db(monkeypatch, tmp_path):
    import database

    monkeypatch.setattr(database, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'assistant.db')
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("PERSONALAYER_DEV_MODE", "1")
    database.create_tables()


def test_personal_assistant_prompt_uses_synthesized_context_only():
    from pcl.assistant import build_personal_assistant_system_prompt
    from pcl.contextlayer import ingest_context_event, update_active_context

    now_ms = int(time.time() * 1000)
    for _ in range(4):
        ingest_context_event(
            {
                "user_id": "user_1",
                "app_id": "figma",
                "feature_id": "auto-layout",
                "action": "used",
                "timestamp": now_ms,
            },
            source="extension",
        )
    update_active_context(
        user_id="user_1",
        project="Design system",
        active_apps=["figma"],
        inferred_intent="adapt_ui",
        session_depth="deep-work",
    )

    prompt, context = build_personal_assistant_system_prompt("user_1")

    assert "personal context assistant" in prompt
    assert "Never reveal raw feature signals" in prompt
    assert "figma" in prompt
    assert "auto-layout" in prompt
    assert "Design system" in prompt
    assert context["bundle"]["active_context"]["project"] == "Design system"
    assert context["top_features"][0]["feature_id"] == "auto-layout"


def test_personal_assistant_prompt_injects_routed_skill_memory():
    from database import upsert_pcl_skill
    from pcl.assistant import build_personal_assistant_system_prompt
    from pcl.memory import write_memory_file

    upsert_pcl_skill(
        skill_id="personal-writing-style",
        name="Personal Writing Style",
        category="writing",
        description="Drafts messages in the user's confirmed tone.",
        instructions="Use voice memory before drafting.",
        allowed_layers=["explicit_preferences", "active_context"],
        memory_scopes=["voice"],
        required_tools=["memory.search"],
        privacy_rules=["never include raw private notes"],
    )
    write_memory_file("user_1", "voice", "# Voice\n\nKeep replies concise and direct.\n")

    prompt, context = build_personal_assistant_system_prompt(
        "user_1",
        message="Write this email reply like me.",
    )

    assert "Selected task skills" in prompt
    assert "personal-writing-style" in prompt
    assert "Use voice memory before drafting" in prompt
    assert "Keep replies concise and direct" in prompt
    assert "never include raw private notes" in prompt
    assert context["skill_route"]["selected_skill_ids"] == ["personal-writing-style"]
    assert context["skill_route"]["memory_scopes"] == ["voice"]


@pytest.mark.asyncio
async def test_assistant_chat_endpoint_returns_dry_run(client):
    async with client as c:
        await c.post("/v1/ingest/sdk", json={
            "user_id": "user_1",
            "app_id": "linear",
            "feature_id": "roadmap",
            "action": "used",
            "timestamp": int(time.time() * 1000),
        })
        response = await c.post("/v1/assistant/chat", json={
            "user_id": "user_1",
            "message": "What should I focus on today?",
        })

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "dry_run"
    assert data["upstream"] == "not_configured"
    assert "ContextLayer data" in data["message"] or "not have enough" in data["message"]
    assert data["payload"]["messages"][0]["role"] == "system"
    assert data["payload"]["messages"][0]["content_length"] > 0
    assert data["payload"]["messages"][1]["content_length"] == len("What should I focus on today?")
    assert "profile" not in data["context"]


@pytest.mark.asyncio
async def test_assistant_chat_dry_run_reports_selected_skills(client):
    async with client as c:
        await c.post("/pcl/skills", json={
            "skill_id": "personal-writing-style",
            "name": "Personal Writing Style",
            "category": "writing",
            "description": "Drafts email replies in the user's tone.",
            "instructions": "Use voice.md before drafting.",
            "allowed_layers": ["explicit_preferences", "active_context"],
            "memory_scopes": ["voice"],
            "required_tools": ["memory.search"],
            "privacy_rules": ["never include raw private notes"],
        })
        await c.put("/v1/memory/voice", json={
            "user_id": "user_1",
            "content": "# Voice\n\nConcise and direct.\n",
        })
        response = await c.post("/v1/assistant/chat", json={
            "user_id": "user_1",
            "message": "Write this email reply like me.",
        })

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "dry_run"
    assert data["context"]["selected_skill_ids"] == ["personal-writing-style"]
    assert data["context"]["memory_scopes"] == ["voice"]
    assert data["context"]["privacy_rules"] == ["never include raw private notes"]
    assert "profile" not in data["context"]


@pytest.mark.asyncio
async def test_assistant_chat_requires_message(client):
    async with client as c:
        response = await c.post("/v1/assistant/chat", json={
            "user_id": "user_1",
            "message": " ",
        })

    assert response.json()["error"] == "message_required"


@pytest.fixture
def client():
    from httpx import AsyncClient
    from main import app

    return AsyncClient(app=app, base_url="http://test")
