from dataclasses import dataclass

from .policies import PolicyRepository
from .schemas import Claim, ClaimReviewResult, Evidence, PolicyCheckResult, RiskAnalysisResult


def mock_policy(claim: Claim, policies: PolicyRepository) -> PolicyCheckResult:
    return policies.check(claim.policy_number, claim.incident_type)


def mock_review(claim: Claim) -> ClaimReviewResult:
    missing = [item for item in claim.required_documents if item not in claim.documents]
    flags = [] if claim.damage_consistent else ["Accident description and damage evidence are inconsistent"]
    return ClaimReviewResult(
        claim_valid=not missing and claim.damage_consistent,
        damage_consistent=claim.damage_consistent,
        estimated_loss=claim.estimated_loss,
        missing_documents=missing,
        red_flags=flags,
        evidence=[Evidence(source_id=f"claim:{claim.claim_id}", quote=claim.description)],
    )


def mock_risk(claim: Claim) -> RiskAnalysisResult:
    high = "multiple_recent_claims" in claim.risk_flags or "conflicting_location" in claim.risk_flags
    medium = bool(claim.risk_flags)
    score = 0.85 if high else 0.45 if medium else 0.12
    return RiskAnalysisResult(
        risk_level="high" if high else "medium" if medium else "low",
        risk_score=score,
        fraud_indicators=claim.risk_flags,
        reasoning="测试数据中的风险标记：" + ("、".join(claim.risk_flags) or "无"),
        evidence=[Evidence(source_id=f"claim:{claim.claim_id}", quote=claim.description)],
    )


@dataclass
class AgentDeps:
    claim: Claim
    policies: PolicyRepository


def create_model_agents(base_url: str, model_name: str, api_key: str):
    from pydantic_ai import Agent, RunContext
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    model = OpenAIChatModel(model_name, provider=OpenAIProvider(base_url=base_url, api_key=api_key))
    policy = Agent(model, deps_type=AgentDeps, output_type=PolicyCheckResult,
        instructions="Check policy coverage using the policy_lookup tool. Cite exact source_id and quote from its output. If no policy or matching explicit clause exists, covered must be null. Never invent clauses.")
    review = Agent(model, deps_type=AgentDeps, output_type=ClaimReviewResult,
        instructions="Review the claim with claim_record. Return required missing documents, inconsistencies and exact claim evidence. Never infer facts outside the record.")
    risk = Agent(model, deps_type=AgentDeps, output_type=RiskAnalysisResult,
        instructions="Assess risk flags from claim_record; do not diagnose fraud. Return low/medium/high, score and record-based evidence. Treat conflicts as high risk.")

    @policy.tool
    async def policy_lookup(ctx: RunContext[AgentDeps]) -> dict:
        """Retrieve the exact coverage clause and citation for this policy and incident."""
        return ctx.deps.policies.check(ctx.deps.claim.policy_number, ctx.deps.claim.incident_type).model_dump()

    @review.tool
    async def claim_record(ctx: RunContext[AgentDeps]) -> dict:
        """Retrieve the claim and uploaded material metadata."""
        return ctx.deps.claim.model_dump()

    @risk.tool
    async def risk_record(ctx: RunContext[AgentDeps]) -> dict:
        """Retrieve risk signals in the claim record."""
        return ctx.deps.claim.model_dump()

    return policy, review, risk
