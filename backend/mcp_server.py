# backend/mcp_server.py
import asyncio
import json
import logging
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

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
    else:
        text = json.dumps({"error": f"Unknown tool: {name}"})

    return [types.TextContent(type="text", text=text)]


# ── Entry point ───────────────────────────────────────────────────────────────

async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
