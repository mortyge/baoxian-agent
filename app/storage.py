import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .schemas import Claim, DecisionResponse
from .seed import sample_claims


class Storage:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS claims (claim_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS decisions (trace_id TEXT PRIMARY KEY, claim_id TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, payload_json TEXT NOT NULL, FOREIGN KEY(claim_id) REFERENCES claims(claim_id))")
            for claim in sample_claims():
                connection.execute("INSERT OR IGNORE INTO claims (claim_id,payload_json) VALUES (?,?)", (claim.claim_id, claim.model_dump_json()))

    def list_claims(self) -> list[Claim]:
        with self.connect() as connection:
            rows = connection.execute("SELECT payload_json FROM claims ORDER BY claim_id").fetchall()
        return [Claim.model_validate_json(row["payload_json"]) for row in rows]

    def get_claim(self, claim_id: str) -> Claim | None:
        with self.connect() as connection:
            row = connection.execute("SELECT payload_json FROM claims WHERE claim_id=?", (claim_id,)).fetchone()
        return Claim.model_validate_json(row["payload_json"]) if row else None

    def create_claim(self, claim: Claim) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO claims (claim_id,payload_json) VALUES (?,?)",
                (claim.claim_id, claim.model_dump_json()),
            )
            return cursor.rowcount == 1

    def save_decision(self, decision: DecisionResponse) -> None:
        with self.connect() as connection:
            connection.execute("INSERT INTO decisions (trace_id,claim_id,payload_json) VALUES (?,?,?)", (decision.trace_id, decision.claim_id, decision.model_dump_json()))

    def decisions(self, claim_id: str) -> list[DecisionResponse]:
        with self.connect() as connection:
            rows = connection.execute("SELECT payload_json FROM decisions WHERE claim_id=? ORDER BY created_at, rowid", (claim_id,)).fetchall()
        return [DecisionResponse.model_validate_json(row["payload_json"]) for row in rows]
