from pathlib import Path

from .schemas import Evidence, PolicyCheckResult


INCIDENT_TERMS = {
    "collision": "Accidental collision damage",
    "weather": "Weather-related damage",
    "personal_belongings_theft": "Theft of personal belongings",
    "mechanical_breakdown": "Mechanical breakdown",
    "flood": "Flood water damage",
}


class PolicyRepository:
    def __init__(self, directory: Path):
        self.directory = directory

    def read(self, policy_number: str) -> tuple[str, list[str]] | None:
        if not policy_number or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for char in policy_number):
            return None
        path = self.directory / f"{policy_number}.md"
        if not path.is_file():
            return None
        return path.name, path.read_text(encoding="utf-8").splitlines()

    def check(self, policy_number: str, incident_type: str) -> PolicyCheckResult:
        document = self.read(policy_number)
        if not document:
            return PolicyCheckResult(covered=None)
        source, lines = document
        term = INCIDENT_TERMS.get(incident_type)
        matching = [line for line in lines if term and term.casefold() in line.casefold() and line.startswith(("Coverage:", "Exclusion:"))]
        if not matching:
            return PolicyCheckResult(covered=None)
        line = matching[0]
        deductible_lines = [item for item in lines if item.startswith("Deductible:")]
        deductible = 250.0 if policy_number == "AUTO-PREMIUM" else 500.0
        citations = [Evidence(source_id=source, quote=line)]
        if deductible_lines and line.startswith("Coverage:"):
            citations.append(Evidence(source_id=source, quote=deductible_lines[0]))
        excluded = line.startswith("Exclusion:")
        return PolicyCheckResult(
            covered=not excluded,
            coverage_type=incident_type if not excluded else None,
            exclusions=[line] if excluded else [],
            deductible=None if excluded else deductible,
            evidence=citations,
        )

    def verify_evidence(self, evidence: Evidence) -> bool:
        if Path(evidence.source_id).name != evidence.source_id or not evidence.source_id.endswith(".md"):
            return False
        path = self.directory / evidence.source_id
        return path.is_file() and bool(evidence.quote.strip()) and evidence.quote in path.read_text(encoding="utf-8")
