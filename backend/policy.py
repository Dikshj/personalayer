import uuid

from database import (
    get_context_contract,
    get_latest_persona,
    insert_context_access_log,
    save_context_contract,
)
from living_persona import build_living_persona


FACILITY_CONTEXT = {
    "inbox_prioritization": {"communication_style", "priority_topics", "negative_preferences", "followup_preferences"},
    "reply_drafting": {"communication_style", "current_goals", "writing_preferences"},
    "newsletter_filtering": {"priority_topics", "negative_preferences"},
    "followup_reminders": {"followup_preferences", "current_goals"},
    "content_recommendations": {"priority_topics", "learning_preferences", "negative_preferences"},
    "search_personalization": {"priority_topics", "current_goals", "learning_preferences"},
    "job_matching": {"career_interests", "skills", "current_goals"},
    "networking": {"career_interests", "communication_style", "current_goals"},
    "product_recommendations": {"priority_topics", "buying_preferences", "negative_preferences"},
}

SENSITIVE_CONTEXT = {
    "raw_email_content",
    "private_contacts",
    "financial_data",
    "health_data",
    "location_history",
    "auth_tokens",
    "full_browsing_history",
}

DEFAULT_ALLOWED = {"communication_style", "priority_topics", "current_goals", "negative_preferences"}


def infer_allowed_context(facilities: list[str]) -> set[str]:
    allowed = set(DEFAULT_ALLOWED)
    for facility in facilities:
        allowed.update(FACILITY_CONTEXT.get(facility, set()))
    return allowed


def negotiate_context_contract(
    platform_type: str,
    facilities: list[str],
    requested_context: list[str] | None = None,
    purpose: str = "",
    retention: str = "session_only",
) -> dict:
    requested = set(requested_context or [])
    allowed_by_facilities = infer_allowed_context(facilities)

    if requested:
        granted = sorted((requested & allowed_by_facilities) - SENSITIVE_CONTEXT)
        denied = sorted((requested - allowed_by_facilities) | (requested & SENSITIVE_CONTEXT))
    else:
        granted = sorted(allowed_by_facilities - SENSITIVE_CONTEXT)
        denied = []

    contract = {
        "contract_id": str(uuid.uuid4()),
        "platform_type": platform_type,
        "facilities": facilities,
        "purpose": purpose,
        "retention": retention,
        "granted_context": granted,
        "denied_context": denied,
        "conditions": {
            "raw_data_shared": False,
            "no_training": True,
            "no_resale": True,
            "scope": "personalization_only",
        },
    }
    save_context_contract(contract)
    return contract


def build_scoped_persona(contract_id: str) -> dict:
    contract = get_context_contract(contract_id)
    if not contract:
        return {"error": "unknown_contract"}
    if contract.get("status") == "revoked":
        insert_context_access_log(
            contract_id=contract_id,
            platform_type=contract["platform_type"],
            action="denied_revoked_contract",
            fields_returned=[],
        )
        return {"error": "contract_revoked", "contract_id": contract_id}

    persona = get_latest_persona() or {}
    living = build_living_persona()
    granted = set(contract["granted_context"])

    scoped = {
        "contract_id": contract_id,
        "platform_type": contract["platform_type"],
        "retention": contract["retention"],
        "conditions": {
            "raw_data_shared": False,
            "personalization_only": True,
        },
        "context": {},
    }

    if "communication_style" in granted:
        scoped["context"]["communication_style"] = persona.get("voice", {})
    if "priority_topics" in granted:
        scoped["context"]["priority_topics"] = living.get("interests", [])[:8]
    if "current_goals" in granted:
        scoped["context"]["current_goals"] = persona.get("context", {})
    if "negative_preferences" in granted:
        scoped["context"]["negative_preferences"] = persona.get("values", {}).get("dislikes", [])
    if "skills" in granted:
        scoped["context"]["skills"] = living.get("skills", [])[:8]
    if "career_interests" in granted:
        scoped["context"]["career_interests"] = {
            "current_project": persona.get("identity", {}).get("current_project", ""),
            "expertise": persona.get("identity", {}).get("expertise", []),
            "work_domains": living.get("work_domains", [])[:6],
        }
    if "learning_preferences" in granted:
        scoped["context"]["learning_preferences"] = {
            "learning_this_week": persona.get("context", {}).get("learning_this_week", []),
            "trends": living.get("trends", [])[:6],
        }
    if "writing_preferences" in granted:
        scoped["context"]["writing_preferences"] = persona.get("voice", {})
    if "followup_preferences" in granted:
        scoped["context"]["followup_preferences"] = {
            "style": "nudge only when related to current goals",
            "default_delay": "3 business days",
        }
    if "buying_preferences" in granted:
        scoped["context"]["buying_preferences"] = {
            "decision_rule": persona.get("decisions", {}).get("optimizes_for", ""),
            "risk_tolerance": persona.get("decisions", {}).get("risk_tolerance", ""),
        }

    insert_context_access_log(
        contract_id=contract_id,
        platform_type=contract["platform_type"],
        action="scoped_persona_returned",
        fields_returned=sorted(scoped["context"].keys()),
    )
    return scoped
