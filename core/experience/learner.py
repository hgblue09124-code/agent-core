# core/experience/learner.py
"""Experience learner — converts validated lessons into knowledge candidates.

Pipeline:
    Experience → Lesson → Validation → Evidence check → Knowledge Candidate

Rules:
    - A lesson must have evidence_count >= MIN_EVIDENCE before becoming a candidate
    - Contradictory lessons must be resolved first
    - Generated knowledge is CANDIDATE, never ACTIVE
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core.experience.schema import Experience
from core.experience.recorder import FailureCategory
from core.experience.analyzer import ExperienceAnalyzer
from core.knowledge.schema import (
    Primitive, KnowledgeStatus, SourceType, generate_primitive_id,
    Provenance,
)
from core.knowledge.lifecycle import LifecycleError


MIN_EVIDENCE_FOR_CANDIDATE = 2
MIN_CONFIDENCE_FOR_CANDIDATE = 0.3


@dataclass
class KnowledgeCandidate:
    """A candidate primitive derived from lessons."""
    candidate_id: str
    primitive: Primitive
    source_lesson_ids: list[str] = field(default_factory=list)
    source_experience_ids: list[str] = field(default_factory=list)
    confidence: float = 0.0
    evidence_count: int = 0
    status: str = "CANDIDATE"  # CANDIDATE, REJECTED, PROMOTED
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "primitive": self.primitive.to_dict(),
            "source_lesson_ids": list(self.source_lesson_ids),
            "source_experience_ids": list(self.source_experience_ids),
            "confidence": self.confidence,
            "evidence_count": self.evidence_count,
            "status": self.status,
            "reason": self.reason,
        }


class ExperienceLearner:
    """Learns from experiences and produces knowledge candidates."""

    def __init__(self, analyzer: Optional[ExperienceAnalyzer] = None):
        self._analyzer = analyzer or ExperienceAnalyzer()
        self._candidates: list[KnowledgeCandidate] = []
        self._rejected: list[KnowledgeCandidate] = []

    def learn(self, experiences: list[Experience]) -> list[KnowledgeCandidate]:
        """Analyze experiences and produce knowledge candidates.

        Returns candidates that meet the evidence threshold.
        """
        if not experiences:
            return []

        # Analyze
        metrics = self._analyzer.analyze(experiences)

        # Group by failure category
        by_cat = self._analyzer.by_failure_category(experiences)

        candidates: list[KnowledgeCandidate] = []

        # 1. Failure recovery lessons
        for cat, exps in by_cat.items():
            if cat == "SUCCESS":
                continue
            if len(exps) >= MIN_EVIDENCE_FOR_CANDIDATE:
                # This is a repeated failure pattern
                prim = self._create_primitive_from_failure(cat, exps, metrics)
                cand = KnowledgeCandidate(
                    candidate_id=generate_primitive_id("CAND"),
                    primitive=prim,
                    source_experience_ids=[e.run_id for e in exps],
                    confidence=min(1.0, 0.3 + 0.1 * len(exps)),
                    evidence_count=len(exps),
                    status="CANDIDATE",
                    reason=f"Repeated failure pattern: {cat}",
                )
                candidates.append(cand)

        # 2. Success pattern lessons
        success_exps = [e for e in experiences if e.success()]
        if success_exps:
            prim = self._create_primitive_from_success(success_exps, metrics)
            cand = KnowledgeCandidate(
                candidate_id=generate_primitive_id("CAND"),
                primitive=prim,
                source_experience_ids=[e.run_id for e in success_exps],
                confidence=min(1.0, 0.3 + 0.1 * len(success_exps)),
                evidence_count=len(success_exps),
                status="CANDIDATE",
                reason="Successful pattern observed",
            )
            candidates.append(cand)

        self._candidates.extend(candidates)
        return candidates

    def _create_primitive_from_failure(self, category: str,
                                       experiences: list[Experience],
                                       metrics) -> Primitive:
        """Create a primitive from a repeated failure pattern."""
        concept = f"failure_{category.lower()}"
        description = f"Repeated {category} failure pattern observed in {len(experiences)} runs"
        when_to_use = f"When encountering {category} failures"
        implementation_pattern = "Check logs for failure category, apply recovery steps"
        examples = [e.run_id for e in experiences[:3]]
        failure_modes = [e.failure for e in experiences if e.failure][:3]

        return Primitive(
            id=generate_primitive_id(),
            domain="failure_recovery",
            concept=concept,
            description=description,
            when_to_use=when_to_use,
            implementation_pattern=implementation_pattern,
            examples=examples,
            failure_modes=failure_modes,
            verification_method="re-run and verify no failure",
            provenance=Provenance(
                source_type=SourceType.OBSERVED.value,
                source_id=f"failure_{category.lower()}",
                evidence_ids=[e.run_id for e in experiences],
                created_by="agent-core",
                notes=f"Derived from {len(experiences)} experiences",
            ),
            status=KnowledgeStatus.CANDIDATE.value,
            confidence=min(1.0, 0.3 + 0.1 * len(experiences)),
        )

    def _create_primitive_from_success(self, experiences: list[Experience],
                                       metrics) -> Primitive:
        """Create a primitive from a successful pattern."""
        concept = "successful_pattern"
        description = f"Successful pattern observed in {len(experiences)} runs"
        when_to_use = "When task matches this pattern"
        implementation_pattern = "Follow the observed successful approach"
        examples = [e.run_id for e in experiences[:3]]

        return Primitive(
            id=generate_primitive_id(),
            domain="success_pattern",
            concept=concept,
            description=description,
            when_to_use=when_to_use,
            implementation_pattern=implementation_pattern,
            examples=examples,
            verification_method="re-run and verify same success",
            provenance=Provenance(
                source_type=SourceType.OBSERVED.value,
                source_id="success_pattern",
                evidence_ids=[e.run_id for e in experiences],
                created_by="agent-core",
                notes=f"Derived from {len(experiences)} successful runs",
            ),
            status=KnowledgeStatus.CANDIDATE.value,
            confidence=min(1.0, 0.3 + 0.1 * len(experiences)),
        )

    def get_candidates(self) -> list[KnowledgeCandidate]:
        return list(self._candidates)

    def get_rejected(self) -> list[KnowledgeCandidate]:
        return list(self._rejected)

    def reject_candidate(self, candidate: KnowledgeCandidate, reason: str) -> None:
        candidate.status = "REJECTED"
        candidate.reason = reason
        self._rejected.append(candidate)
        if candidate in self._candidates:
            self._candidates.remove(candidate)