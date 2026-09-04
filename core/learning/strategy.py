# core/learning/strategy.py
"""Strategy schema — first-class persistent strategy model and applications for Agent-Core."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class StrategyStatus(str, Enum):
    CANDIDATE = "CANDIDATE"      # Newly extracted from lesson; unvalidated
    VALIDATED = "VALIDATED"      # Tested once or twice successfully; rising confidence
    SUPPORTED = "SUPPORTED"      # High confidence; active default recommendation
    WEAKENED  = "WEAKENED"       # Recent failures; reduced weight/recommendation
    RETIRED   = "RETIRED"        # Ineffective; inactive and non-binding
    SUPERSEDED = "SUPERSEDED"    # Replaced by a newer versioned strategy


@dataclass
class StrategyApplication:
    """Record of a single strategy application attempt and outcome."""

    application_id: str
    strategy_id: str
    run_id: str
    task_id: str
    context: dict = field(default_factory=dict)
    expected_outcome: str = ""
    actual_outcome: str = ""
    verification_result: str = "PASS"  # PASS | FAIL | INCONCLUSIVE
    applied_at: str = ""


@dataclass
class Strategy:
    """First-class persistent Strategy model representing learned behavioral rules."""

    strategy_id: str
    name: str
    description: str
    rule: str
    applicable_context: str = ""
    prerequisites: list[str] = field(default_factory=list)
    expected_outcome: str = ""
    evidence: list[str] = field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    inconclusive_count: int = 0
    confidence: float = 0.3  # Initial confidence for CANDIDATE (0.0 to 1.0)
    status: str = StrategyStatus.CANDIDATE.value
    version: int = 1
    provenance: str = ""     # Source lesson ID or experience ID
    source_experiences: list[str] = field(default_factory=list)
    supersedes: Optional[str] = None
    superseded_by: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "description": self.description,
            "rule": self.rule,
            "applicable_context": self.applicable_context,
            "prerequisites": list(self.prerequisites),
            "expected_outcome": self.expected_outcome,
            "evidence": list(self.evidence),
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "inconclusive_count": self.inconclusive_count,
            "confidence": round(self.confidence, 4),
            "status": self.status,
            "version": self.version,
            "provenance": self.provenance,
            "source_experiences": list(self.source_experiences),
            "supersedes": self.supersedes,
            "superseded_by": self.superseded_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: dict) -> Strategy:
        return cls(
            strategy_id=d["strategy_id"],
            name=d.get("name", ""),
            description=d.get("description", ""),
            rule=d.get("rule", ""),
            applicable_context=d.get("applicable_context", ""),
            prerequisites=list(d.get("prerequisites", [])),
            expected_outcome=d.get("expected_outcome", ""),
            evidence=list(d.get("evidence", [])),
            success_count=int(d.get("success_count", 0)),
            failure_count=int(d.get("failure_count", 0)),
            inconclusive_count=int(d.get("inconclusive_count", 0)),
            confidence=float(d.get("confidence", 0.3)),
            status=d.get("status", StrategyStatus.CANDIDATE.value),
            version=int(d.get("version", 1)),
            provenance=d.get("provenance", ""),
            source_experiences=list(d.get("source_experiences", [])),
            supersedes=d.get("supersedes"),
            superseded_by=d.get("superseded_by"),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            metadata=dict(d.get("metadata", {})),
        )

    def is_active(self) -> bool:
        """Returns True if strategy is in an active state."""
        return self.status in (StrategyStatus.VALIDATED.value, StrategyStatus.SUPPORTED.value)

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()
