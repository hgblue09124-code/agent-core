# core/philosophy/schema.py
"""Agent Philosophy Data Schema v1.0.

Philosophy represents soft behavioral tendencies derived from experience and human teaching.
It is NOT a Constitution, hard rule engine, or policy validator.

Precedence:
Kernel / Security / Contracts > Verification requirements > Explicit task requirements > Philosophy / behavioral tendencies
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class PhilosophyStatus(str, Enum):
    CANDIDATE = "candidate"
    SUPPORTED = "supported"
    WEAKENED = "weakened"
    REJECTED = "rejected"
    RETIRED = "retired"


class TeachingType(str, Enum):
    TEACH = "teach"
    CHALLENGE = "challenge"
    SUPPORT = "support"
    CONTRADICT = "contradict"
    MODIFY = "modify"
    REJECT = "reject"
    RETIRE = "retire"


@dataclass
class EvolutionRecord:
    """Audit record tracking how a philosophy tendency evolves over time."""

    timestamp: str
    from_status: str
    to_status: str
    reason: str
    confidence_delta: float
    actor: str = "human"  # 'human' | 'experience' | 'lesson'
    action_type: str = TeachingType.TEACH.value

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "reason": self.reason,
            "confidence_delta": round(self.confidence_delta, 4),
            "actor": self.actor,
            "action_type": self.action_type,
        }

    @classmethod
    def from_dict(cls, d: dict) -> EvolutionRecord:
        return cls(
            timestamp=d.get("timestamp", ""),
            from_status=d.get("from_status", PhilosophyStatus.CANDIDATE.value),
            to_status=d.get("to_status", PhilosophyStatus.CANDIDATE.value),
            reason=d.get("reason", ""),
            confidence_delta=float(d.get("confidence_delta", 0.0)),
            actor=d.get("actor", "human"),
            action_type=d.get("action_type", TeachingType.TEACH.value),
        )


@dataclass
class PhilosophyTendency:
    """Minimal, extensible representation for an Agent behavioral tendency."""

    tendency_id: str
    statement: str
    origin: str
    supporting_evidence_ids: list[str] = field(default_factory=list)
    contradicting_evidence_ids: list[str] = field(default_factory=list)
    confidence: float = 0.3
    status: str = PhilosophyStatus.CANDIDATE.value
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    evolution_history: list[EvolutionRecord] = field(default_factory=list)
    source_lesson_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "tendency_id": self.tendency_id,
            "statement": self.statement,
            "origin": self.origin,
            "supporting_evidence_ids": list(self.supporting_evidence_ids),
            "contradicting_evidence_ids": list(self.contradicting_evidence_ids),
            "confidence": round(max(0.0, min(1.0, self.confidence)), 4),
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "evolution_history": [rec.to_dict() for rec in self.evolution_history],
            "source_lesson_ids": list(self.source_lesson_ids),
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, d: dict) -> PhilosophyTendency:
        return cls(
            tendency_id=d["tendency_id"],
            statement=d.get("statement", ""),
            origin=d.get("origin", ""),
            supporting_evidence_ids=list(d.get("supporting_evidence_ids", [])),
            contradicting_evidence_ids=list(d.get("contradicting_evidence_ids", [])),
            confidence=float(d.get("confidence", 0.3)),
            status=d.get("status", PhilosophyStatus.CANDIDATE.value),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            evolution_history=[
                EvolutionRecord.from_dict(r) for r in d.get("evolution_history", [])
            ],
            source_lesson_ids=list(d.get("source_lesson_ids", [])),
            tags=list(d.get("tags", [])),
        )

    def is_active_preference(self, include_weakened: bool = False) -> bool:
        """Returns True if the tendency can act as a soft behavioral preference.

        Rules:
        - CANDIDATE: False (forming seeds do NOT influence behavior).
        - SUPPORTED: True (established preferences, if confidence >= 0.2).
        - WEAKENED: False by default (only True if include_weakened=True).
        - REJECTED / RETIRED: False.
        """
        if self.status == PhilosophyStatus.SUPPORTED.value:
            return self.confidence >= 0.2
        if include_weakened and self.status == PhilosophyStatus.WEAKENED.value:
            return self.confidence >= 0.1
        return False
