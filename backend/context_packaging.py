"""Compatibility layer for scoped context contracts.

The public API and MCP server import this module directly; the implementation
now lives in policy.py.
"""

from policy import build_scoped_persona, negotiate_context_contract


def create_context_contract(
    platform_type: str,
    facilities: list[str],
    requested_context: list[str] | None = None,
    purpose: str = "",
    retention: str = "session_only",
) -> dict:
    return negotiate_context_contract(
        platform_type=platform_type,
        facilities=facilities,
        requested_context=requested_context,
        purpose=purpose,
        retention=retention,
    )


def build_context_package(contract_id: str) -> dict:
    return build_scoped_persona(contract_id)
