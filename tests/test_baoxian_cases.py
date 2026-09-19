"""Regression coverage using representative insurance claim scenarios.

The source material is copied into a Chinese fixture so tests remain offline,
reviewable, and independent of the downloaded repository path.
"""

import json
from pathlib import Path

from fastapi.testclient import TestClient


FIXTURE = Path(__file__).parent / "fixtures" / "baoxian_cases_zh.json"


def test_baoxian_cases_are_translated_and_decidable(tmp_path):
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(data["evaluation_queries"]) == 5
    assert all("query" in item and "ground_truth" in item for item in data["evaluation_queries"])
    assert all(any("\u4e00" <= char <= "\u9fff" for char in item["query"]) for item in data["evaluation_queries"])
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()
    for policy_number, content in data["policies"].items():
        (policy_dir / f"{policy_number}.md").write_text(content, encoding="utf-8")

    from app.main import create_app

    with TestClient(create_app(db_path=tmp_path / "claims.sqlite3", policy_dir=policy_dir)) as client:
        for case in data["cases"]:
            claim = {key: case[key] for key in (
                "claim_id", "customer_id", "policy_number", "incident_type",
                "description", "estimated_loss", "documents",
                "required_documents", "damage_consistent", "risk_flags",
            )}
            created = client.post("/v1/claims", json=claim)
            assert created.status_code == 201, created.text
            result = client.post(f"/v1/claims/{case['claim_id']}/decide")
            assert result.status_code == 200, result.text
            payload = result.json()
            assert payload["decision"] == case["expected_decision"]
            assert payload["agent_reports"]["review"]["evidence"][0]["quote"] == case["description"]
            assert payload["trace_id"]

        assert client.get("/v1/claims").json()
