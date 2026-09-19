import asyncio
import os
from uuid import uuid4

from .agents import AgentDeps, create_model_agents, mock_policy, mock_review, mock_risk
from .policies import PolicyRepository
from .schemas import AgentReports, Claim, DecisionResponse


class ModelAssessmentError(Exception):
    pass


def decision_gate(reports: AgentReports) -> tuple[str, str]:
    policy, review, risk = reports.policy, reports.review, reports.risk
    if review.missing_documents:
        return "NEED_MORE_INFO", "缺少必要材料：" + "、".join(review.missing_documents)
    if policy.covered is None or not policy.evidence:
        return "HUMAN_REVIEW", "无法依据可核验的保单条款确认是否承保，需要人工复核。"
    if risk.risk_level == "high" or review.red_flags or not review.damage_consistent or not review.claim_valid:
        return "HUMAN_REVIEW", "风险信号或案件材料存在不一致，需要人工复核。"
    if policy.covered is False:
        return "DENIED", "已核验的保单条款明确排除此类事故。"
    if risk.fraud_indicators and risk.risk_level == "low":
        return "HUMAN_REVIEW", "存在风险指标，需要人工核实。"
    return "APPROVED", "已有保单承保条款证据，必要材料齐全，且未触发升级规则；本结果仅为审核建议。"


class ClaimService:
    def __init__(self, policies: PolicyRepository, mode: str = "mock"):
        if mode not in {"mock", "ollama"}:
            raise ValueError("INSURANCE_AGENT_MODE must be mock or ollama")
        self.policies = policies
        self.mode = mode
        self.model_agents = None
        if mode == "ollama":
            self.model_agents = create_model_agents(
                os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
                os.getenv("OLLAMA_MODEL", "qwen3:8b"),
                os.getenv("OLLAMA_API_KEY", "ollama"),
            )

    async def assess(self, claim: Claim) -> DecisionResponse:
        if self.model_agents:
            deps = AgentDeps(claim, self.policies)
            prompt = f"Assess only claim {claim.claim_id}. Call the supplied tool."
            try:
                results = await asyncio.gather(*(agent.run(prompt, deps=deps) for agent in self.model_agents))
                reports = AgentReports(policy=results[0].output, review=results[1].output, risk=results[2].output)
                self._verify_model_reports(claim, reports)
            except Exception as exc:
                raise ModelAssessmentError("Model assessment failed or contradicted verified source data") from exc
        else:
            async def policy_check():
                return mock_policy(claim, self.policies)

            async def claim_review():
                return mock_review(claim)

            async def risk_analysis():
                return mock_risk(claim)

            policy, review, risk = await asyncio.gather(policy_check(), claim_review(), risk_analysis())
            reports = AgentReports(policy=policy, review=review, risk=risk)

        status, reason = decision_gate(reports)
        evidence = list(reports.policy.evidence) + list(reports.review.evidence) + list(reports.risk.evidence)
        return DecisionResponse(
            claim_id=claim.claim_id,
            policy_number=claim.policy_number,
            decision=status,
            reason=reason,
            evidence=evidence,
            agent_reports=reports,
            trace_id=str(uuid4()),
        )

    def _verify_model_reports(self, claim: Claim, reports: AgentReports) -> None:
        verified = self.policies.check(claim.policy_number, claim.incident_type)
        if reports.policy.covered != verified.covered or reports.policy.exclusions != verified.exclusions:
            raise ValueError("Model policy result contradicts actual clause")
        if reports.policy.coverage_type != verified.coverage_type or reports.policy.deductible != verified.deductible:
            raise ValueError("Model misreported policy conditions")
        if verified.covered is not None and verified.evidence[0] not in reports.policy.evidence:
            raise ValueError("Missing incident-specific policy citation")
        if any(evidence not in verified.evidence for evidence in reports.policy.evidence):
            raise ValueError("Unverified or unrelated policy citation")
        if reports.policy.covered is None and reports.policy.evidence:
            raise ValueError("Cannot cite unknown coverage")
        missing = [item for item in claim.required_documents if item not in claim.documents]
        if reports.review.missing_documents != missing:
            raise ValueError("Model misreported required documents")
        if reports.review.damage_consistent != claim.damage_consistent:
            raise ValueError("Model misreported damage consistency")
        if reports.risk.risk_level != mock_risk(claim).risk_level:
            raise ValueError("Model misreported hard risk category")
        valid_claim_quotes = {claim.description}
        for evidence in reports.review.evidence + reports.risk.evidence:
            if evidence.source_id != f"claim:{claim.claim_id}" or evidence.quote not in valid_claim_quotes:
                raise ValueError("Unverified claim evidence")
