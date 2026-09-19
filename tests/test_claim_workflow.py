"""Offline acceptance tests for the first claims decision workflow."""

import os
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


EXPECTED_DECISIONS = {
    "CL001": "APPROVED",  # covered, valid, low risk
    "CL002": "APPROVED",  # covered, valid, medium risk
    "CL003": "DENIED",  # no applicable coverage
    "CL004": "DENIED",  # explicit exclusion
    "CL005": "DENIED",  # explicit mechanical-breakdown exclusion
    "CL006": "NEED_MORE_INFO",  # missing claim material
    "CL007": "NEED_MORE_INFO",  # missing accident statement
    "CL008": "HUMAN_REVIEW",  # high risk
    "CL009": "HUMAN_REVIEW",  # material red flag
    "CL010": "HUMAN_REVIEW",  # policy cannot be verified
}


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("claims") / "claims.sqlite3"
    old_mode = os.environ.get("INSURANCE_AGENT_MODE")
    old_db = os.environ.get("INSURANCE_AGENT_DB_PATH")
    os.environ["INSURANCE_AGENT_MODE"] = "mock"
    os.environ["INSURANCE_AGENT_DB_PATH"] = str(db_path)
    try:
        from app.main import create_app

        with TestClient(create_app(db_path=db_path, mode="mock")) as test_client:
            yield test_client
    finally:
        if old_mode is None:
            os.environ.pop("INSURANCE_AGENT_MODE", None)
        else:
            os.environ["INSURANCE_AGENT_MODE"] = old_mode
        if old_db is None:
            os.environ.pop("INSURANCE_AGENT_DB_PATH", None)
        else:
            os.environ["INSURANCE_AGENT_DB_PATH"] = old_db


def test_health_and_seeded_claims(client):
    assert client.get("/health").status_code == 200
    response = client.get("/v1/claims")
    assert response.status_code == 200
    payload = response.json()
    claims = payload if isinstance(payload, list) else payload["claims"]
    assert EXPECTED_DECISIONS.keys() <= {claim["claim_id"] for claim in claims}


@pytest.mark.parametrize("claim_id,expected", EXPECTED_DECISIONS.items())
def test_decision_case_and_audit(client, claim_id, expected):
    claim_response = client.get(f"/v1/claims/{claim_id}")
    assert claim_response.status_code == 200
    claim = claim_response.json()
    assert claim["claim_id"] == claim_id

    response = client.post(f"/v1/claims/{claim_id}/decide")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["claim_id"] == claim_id
    assert result["policy_number"] == claim["policy_number"]
    assert result["decision"] == expected
    assert result["reason"].strip()
    assert result["trace_id"].strip()
    assert set(result["agent_reports"]) == {"policy", "review", "risk"}
    assert isinstance(result["evidence"], list)
    for citation in result["evidence"]:
        assert citation["source_id"].strip()
        assert citation["quote"].strip()

    policy_report = result["agent_reports"]["policy"]
    if claim_id == "CL010":
        assert policy_report["covered"] is None
        assert not policy_report["evidence"]
    else:
        assert policy_report["evidence"]
        policy_file = Path(__file__).resolve().parents[1] / "data" / "policies" / f"{claim['policy_number']}.md"
        source_text = policy_file.read_text(encoding="utf-8")
        for citation in policy_report["evidence"]:
            assert citation["source_id"] == policy_file.name
            assert citation["quote"] in source_text

    expected_policy_clause = {
        "CL001": "Accidental collision damage",
        "CL002": "Weather-related damage",
        "CL003": "Flood water damage",
        "CL004": "Theft of personal belongings",
        "CL005": "Mechanical breakdown",
    }
    if claim_id in expected_policy_clause:
        assert expected_policy_clause[claim_id] in policy_report["evidence"][0]["quote"]
        assert policy_report["covered"] is (expected == "APPROVED")

    if claim_id in ("CL006", "CL007"):
        assert result["agent_reports"]["review"]["missing_documents"]
    if claim_id == "CL008":
        assert result["agent_reports"]["risk"]["risk_level"] == "high"
    if claim_id == "CL009":
        assert result["agent_reports"]["review"]["red_flags"] or result["agent_reports"]["risk"]["fraud_indicators"]

    audit_response = client.get(f"/v1/claims/{claim_id}/decisions")
    assert audit_response.status_code == 200
    payload = audit_response.json()
    entries = payload if isinstance(payload, list) else payload["decisions"]
    assert any(
        entry["trace_id"] == result["trace_id"]
        and entry["decision"] == expected
        for entry in entries
    )
    with sqlite3.connect(os.environ["INSURANCE_AGENT_DB_PATH"]) as connection:
        row = connection.execute(
            "SELECT claim_id, payload_json FROM decisions WHERE trace_id=?", (result["trace_id"],)
        ).fetchone()
    assert row is not None
    assert row[0] == claim_id
    assert json.loads(row[1]) == result


@pytest.mark.parametrize("path", ["/v1/claims/DOES-NOT-EXIST", "/v1/claims/DOES-NOT-EXIST/decisions"])
def test_unknown_claim_is_not_fabricated(client, path):
    assert client.get(path).status_code == 404


def test_unknown_claim_cannot_be_decided(client):
    assert client.post("/v1/claims/DOES-NOT-EXIST/decide").status_code == 404


def test_new_claim_can_be_created_decided_and_audited(client):
    claim = {
        "claim_id": "NEW-CASE-001",
        "policy_number": "AUTO-BASIC",
        "customer_id": "NEW-CUSTOMER-001",
        "incident_type": "collision",
        "description": "A reversing vehicle struck the insured rear bumper.",
        "estimated_loss": 2100,
        "documents": ["statement", "repair_estimate"],
        "required_documents": ["statement", "repair_estimate"],
        "damage_consistent": True,
        "risk_flags": [],
    }
    created = client.post("/v1/claims", json=claim)
    assert created.status_code == 201, created.text
    assert created.json() == claim
    assert client.get("/v1/claims/NEW-CASE-001").json() == claim
    assert client.post("/v1/claims", json=claim).status_code == 409

    decision = client.post("/v1/claims/NEW-CASE-001/decide")
    assert decision.status_code == 200, decision.text
    result = decision.json()
    assert result["decision"] == "APPROVED"
    assert result["agent_reports"]["policy"]["covered"] is True
    assert any("Accidental collision damage" in item["quote"] for item in result["evidence"])
    assert client.get("/v1/claims/NEW-CASE-001/decisions").json() == [result]

    invalid = dict(claim, claim_id="NEW-CASE-INVALID", estimated_loss=-1)
    assert client.post("/v1/claims", json=invalid).status_code == 422
    assert client.get("/v1/claims/NEW-CASE-INVALID").status_code == 404


def test_repeat_decision_preserves_both_audit_entries(client):
    before = client.get("/v1/claims/CL001/decisions").json()
    first = client.post("/v1/claims/CL001/decide").json()
    second = client.post("/v1/claims/CL001/decide").json()
    after = client.get("/v1/claims/CL001/decisions").json()
    assert len(after) == len(before) + 2
    assert first["trace_id"] != second["trace_id"]
    assert first["decision"] == second["decision"] == "APPROVED"
    assert first["agent_reports"] == second["agent_reports"]
    assert first["evidence"] == second["evidence"]
    assert {first["trace_id"], second["trace_id"]} <= {item["trace_id"] for item in after}


def test_missing_policy_is_not_treated_as_a_known_exclusion(client):
    excluded = client.post("/v1/claims/CL004/decide").json()
    missing = client.post("/v1/claims/CL010/decide").json()
    assert excluded["agent_reports"]["policy"]["covered"] is False
    assert missing["agent_reports"]["policy"]["covered"] is None
    assert excluded["decision"] == "DENIED"
    assert missing["decision"] == "HUMAN_REVIEW"


def test_missing_material_precedes_high_risk():
    from app.agents import mock_policy, mock_review, mock_risk
    from app.policies import PolicyRepository
    from app.schemas import AgentReports
    from app.seed import sample_claims
    from app.service import decision_gate

    high_risk_claim = sample_claims()[7]
    incomplete = high_risk_claim.model_copy(update={"documents": ["statement"]})
    reports = AgentReports(
        policy=mock_policy(incomplete, PolicyRepository(Path(__file__).resolve().parents[1] / "data" / "policies")),
        review=mock_review(incomplete),
        risk=mock_risk(incomplete),
    )
    assert reports.review.missing_documents == ["repair_estimate"]
    assert reports.risk.risk_level == "high"
    assert decision_gate(reports)[0] == "NEED_MORE_INFO"


def test_model_failure_does_not_create_approval_or_audit(tmp_path, monkeypatch):
    from app import service
    from app.main import create_app

    class FailedModelAgent:
        async def run(self, prompt, deps):
            raise RuntimeError("model unavailable")

    monkeypatch.setattr(service, "create_model_agents", lambda *_args: (FailedModelAgent(),) * 3)
    with TestClient(create_app(db_path=tmp_path / "failed.sqlite3", mode="ollama")) as failing_client:
        response = failing_client.post("/v1/claims/CL001/decide")
        assert response.status_code == 503
        assert failing_client.get("/v1/claims/CL001/decisions").json() == []


def test_pydantic_ai_agents_can_be_built_without_ollama():
    from pydantic_ai import Agent
    from app.agents import create_model_agents

    agents = create_model_agents("http://localhost:11434/v1", "qwen3:8b", "ollama")
    assert len(agents) == 3
    assert all(isinstance(agent, Agent) for agent in agents)


def test_model_contradicting_policy_cannot_approve_or_audit(tmp_path, monkeypatch):
    from app import service
    from app.agents import mock_review, mock_risk
    from app.main import create_app
    from app.schemas import PolicyCheckResult
    from app.seed import sample_claims

    class ContradictingAgent:
        def __init__(self, output):
            self.output = output

        async def run(self, prompt, deps):
            return SimpleNamespace(output=self.output)

    claim = sample_claims()[3]  # CL004 has a cited explicit exclusion.
    monkeypatch.setattr(service, "create_model_agents", lambda *_args: (
        ContradictingAgent(PolicyCheckResult(covered=True)),
        ContradictingAgent(mock_review(claim)),
        ContradictingAgent(mock_risk(claim)),
    ))
    with TestClient(create_app(db_path=tmp_path / "contradiction.sqlite3", mode="ollama")) as failing_client:
        response = failing_client.post("/v1/claims/CL004/decide")
        assert response.status_code == 503
        assert failing_client.get("/v1/claims/CL004/decisions").json() == []


def test_real_but_unrelated_policy_quote_cannot_support_approval(tmp_path, monkeypatch):
    from app import service
    from app.agents import mock_review, mock_risk
    from app.main import create_app
    from app.schemas import Evidence, PolicyCheckResult
    from app.seed import sample_claims

    class FabricatedAgent:
        def __init__(self, output):
            self.output = output

        async def run(self, prompt, deps):
            return SimpleNamespace(output=self.output)

    claim = sample_claims()[0]
    unrelated_quote = "Deductible: 500 currency units per collision claim."
    assert unrelated_quote in (Path(__file__).resolve().parents[1] / "data" / "policies" / "AUTO-BASIC.md").read_text(encoding="utf-8")
    monkeypatch.setattr(service, "create_model_agents", lambda *_args: (
        FabricatedAgent(PolicyCheckResult(
            covered=True, coverage_type="collision", deductible=500,
            evidence=[Evidence(source_id="AUTO-BASIC.md", quote=unrelated_quote)],
        )),
        FabricatedAgent(mock_review(claim)),
        FabricatedAgent(mock_risk(claim)),
    ))
    with TestClient(create_app(db_path=tmp_path / "irrelevant.sqlite3", mode="ollama")) as failing_client:
        response = failing_client.post("/v1/claims/CL001/decide")
        assert response.status_code == 503
        assert failing_client.get("/v1/claims/CL001/decisions").json() == []


def test_first_version_has_no_azure_or_langgraph_runtime_dependency():
    root = Path(__file__).resolve().parents[1]
    pyproject = root / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8").lower()
    assert "langgraph" not in text
    assert "azure-" not in text
    assert "pydantic-ai" in text
    for source in (root / "app").rglob("*.py"):
        code = source.read_text(encoding="utf-8").lower()
        assert "import langgraph" not in code, source
        assert "import azure" not in code, source
