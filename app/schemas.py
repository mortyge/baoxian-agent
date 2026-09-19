from typing import Literal

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    source_id: str
    quote: str


class PolicyCheckResult(BaseModel):
    covered: bool | None
    coverage_type: str | None = None
    exclusions: list[str] = Field(default_factory=list)
    deductible: float | None = None
    evidence: list[Evidence] = Field(default_factory=list)


class ClaimReviewResult(BaseModel):
    claim_valid: bool
    damage_consistent: bool
    estimated_loss: float | None = None
    missing_documents: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


class RiskAnalysisResult(BaseModel):
    risk_level: Literal["low", "medium", "high"]
    risk_score: float = Field(ge=0, le=1)
    fraud_indicators: list[str] = Field(default_factory=list)
    reasoning: str
    evidence: list[Evidence] = Field(default_factory=list)


Decision = Literal["APPROVED", "DENIED", "NEED_MORE_INFO", "HUMAN_REVIEW"]


class AgentReports(BaseModel):
    policy: PolicyCheckResult
    review: ClaimReviewResult
    risk: RiskAnalysisResult


class DecisionResponse(BaseModel):
    claim_id: str
    policy_number: str
    decision: Decision
    reason: str
    evidence: list[Evidence]
    agent_reports: AgentReports
    trace_id: str


class Claim(BaseModel):
    claim_id: str
    policy_number: str
    incident_type: str
    description: str
    estimated_loss: float = Field(ge=0)
    documents: list[str]
    required_documents: list[str]
    damage_consistent: bool
    risk_flags: list[str]
    customer_id: str


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)


class ChatResponse(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str
    decision: Decision | None = None
    claim_id: str | None = None
    trace_id: str | None = None
