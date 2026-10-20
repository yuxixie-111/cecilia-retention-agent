from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RiskBand = Literal["low", "medium", "high"]


class ClinicProfile(BaseModel):
    clinic_id: str
    segment: str
    region: str
    clinic_notes: str = ""
    stocked_cabinets: int
    active_cabinet_ratio_30d: float
    buyer_count: int
    tenure_months: int
    monthly_contract_value: float
    orders_30d: int
    order_change_pct: float
    service_tickets_90d: int
    nps: int
    days_to_term: int
    invoice_failures_90d: int
    stocking_complete: bool
    service_ticket_rate: float
    activity_score: float
    term_pressure: float
    value_at_risk: float
    lapsed: int | None = None


class RiskDriver(BaseModel):
    feature: str
    clinic_value: str | float | int | bool
    baseline_value: str | float | int | bool
    probability_impact: float
    direction: Literal["risk", "protective"]
    explanation: str


class PredictionResult(BaseModel):
    clinic_id: str
    lapse_probability: float = Field(ge=0, le=1)
    risk_band: RiskBand
    top_drivers: list[RiskDriver]
    model_version: str


class KnowledgeHit(BaseModel):
    document: str
    section: str
    score: float
    text: str


class MemoryItem(BaseModel):
    memory_id: int | None = None
    clinic_id: str
    memory_type: str
    content: str
    importance: float = Field(default=0.5, ge=0, le=1)
    created_at: datetime | None = None


class ActionItem(BaseModel):
    priority: int
    action: str
    owner: str
    rationale: str
    expected_impact: str
    approval_required: bool = False


class Recommendation(BaseModel):
    executive_summary: str
    actions: list[ActionItem]
    do_not_do: list[str]
    evidence: list[str]
    confidence: float = Field(ge=0, le=1)
    generated_by: str
    risk_assessment: str = ""
    recommended_actions: list[str] = Field(default_factory=list)
    rationale: str = ""
    requires_human_approval: bool = False


class ReviewResult(BaseModel):
    passed: bool
    score: float = Field(ge=0, le=1)
    issues: list[str]
    required_changes: list[str]


class AnalysisResponse(BaseModel):
    analysis_id: str
    session_id: str
    clinic: ClinicProfile
    prediction: PredictionResult
    benchmark: dict[str, float | int | str]
    knowledge: list[KnowledgeHit]
    memories_used: list[MemoryItem]
    recommendation: Recommendation
    review: ReviewResult
    report_markdown: str
    ticket_id: int | None = None
    latency_ms: float
    provider: str = ""
    model: str = ""
    requested_provider: str = ""
    generation_mode: str = "deterministic"
    provider_available: bool = True
    ollama_available: bool = True
    fallback_used: bool = False
    fallback_reason: str | None = None
    llm_latency_ms: float | None = None
    last_successful_llm_call: str | None = None


class Feedback(BaseModel):
    analysis_id: str
    rating: int = Field(ge=1, le=5)
    comment: str = ""


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8_000)


class ChatResult(BaseModel):
    answer: str
    provider: str
    model: str
    generation_mode: str
    tools_used: list[str] = Field(default_factory=list)
    fallback_used: bool = False
    fallback_reason: str | None = None
    latency_ms: float | None = None
