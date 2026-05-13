from typing import Any, Literal

from pydantic import BaseModel, Field


ContextLayer = Literal[
    "identity_role",
    "capability_signals",
    "behavior_patterns",
    "active_context",
    "explicit_preferences",
]


class IdentityRole(BaseModel):
    role: str = ""
    domain: str = ""
    skill_level: str = ""
    current_project: str = ""
    expertise: list[str] = Field(default_factory=list)


class CapabilitySignal(BaseModel):
    feature_id: str
    feature_name: str = ""
    use_count: int = 0
    last_used_at: int | None = None
    recency_weight: float = 0.0
    confidence: float = 0.0


class BehaviorPatterns(BaseModel):
    active_hours: str = ""
    session_length: str = ""
    workflow_style: str = ""
    preferred_depth: Literal["minimal", "balanced", "detailed", "unknown"] = "unknown"


class ActiveContext(BaseModel):
    current_project: str = ""
    active_tools: list[str] = Field(default_factory=list)
    current_goal: str = ""
    blockers: list[str] = Field(default_factory=list)


class ExplicitPreference(BaseModel):
    key: str
    value: Any
    hard_rule: bool = True
    source: str = "user"


class UserContextProfile(BaseModel):
    user_id: str
    identity: IdentityRole = Field(default_factory=IdentityRole)
    capabilities: list[CapabilitySignal] = Field(default_factory=list)
    behavior: BehaviorPatterns = Field(default_factory=BehaviorPatterns)
    active_context: ActiveContext = Field(default_factory=ActiveContext)
    explicit_preferences: list[ExplicitPreference] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class AppFeature(BaseModel):
    feature_id: str
    name: str
    category: str = ""
    required_context: list[ContextLayer] = Field(default_factory=list)


class ContextQuery(BaseModel):
    app_id: str
    user_id: str
    purpose: str = "ui_personalization"
    requested_layers: list[ContextLayer] = Field(default_factory=list)
    features: list[AppFeature] = Field(default_factory=list)


class RankedFeature(BaseModel):
    feature_id: str
    name: str
    rank: int
    score: float
    reason_codes: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class DecisionBundle(BaseModel):
    app_id: str
    user_id: str
    purpose: str
    allowed_layers: list[ContextLayer]
    ranked_features: list[RankedFeature]
    constraints: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    audit: dict[str, Any] = Field(default_factory=dict)
