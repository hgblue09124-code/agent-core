# core/experience/promotion.py
"""Experience → Knowledge promotion bridge.

Promotes validated lessons into knowledge primitives.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core.experience.learner import KnowledgeCandidate, ExperienceLearner
from core.experience.schema import Experience
from core.knowledge.engine import KnowledgeEngine
from core.knowledge.schema import KnowledgeStatus, Primitive
from core.knowledge.lifecycle import LifecycleError


@dataclass
class PromotionResult:
    """Result of promoting a lesson to knowledge."""
    candidate_id: str
    primitive_id: str
    promoted: bool
    reason: str
    old_status: str = ""
    new_status: str = ""


class ExperiencePromoter:
    """Promotes experience lessons into knowledge primitives."""

    def __init__(self, knowledge_engine: KnowledgeEngine):
        self._knowledge = knowledge_engine
        self._learner = ExperienceLearner()
        self._results: list[PromotionResult] = []

    def promote(self, experiences: list[Experience]) -> list[PromotionResult]:
        """Promote lessons from experiences into knowledge primitives.

        Returns a list of PromotionResult for each candidate.
        """
        candidates = self._learner.learn(experiences)
        results: list[PromotionResult] = []

        for cand in candidates:
            try:
                # Create primitive in knowledge engine
                prim = self._knowledge.create_primitive(
                    domain=cand.primitive.domain,
                    concept=cand.primitive.concept,
                    description=cand.primitive.description,
                    when_to_use=cand.primitive.when_to_use,
                    implementation_pattern=cand.primitive.implementation_pattern,
                    examples=cand.primitive.examples,
                    prerequisites=cand.primitive.prerequisites,
                    failure_modes=cand.primitive.failure_modes,
                    verification_method=cand.primitive.verification_method,
                    source_type=cand.primitive.provenance.source_type,
                    source_id=cand.primitive.provenance.source_id,
                    evidence_ids=cand.primitive.provenance.evidence_ids,
                    created_by=cand.primitive.provenance.created_by,
                    notes=cand.primitive.provenance.notes,
                    run_id=cand.primitive.provenance.run_id,
                )
                # Validate and promote
                prim, _ = self._knowledge.validate_primitive(prim, reason="Experience-derived")
                prim, _ = self._knowledge.verify_primitive(prim, evidence_id=cand.candidate_id)
                prim.confidence = cand.confidence
                self._knowledge.update_primitive(prim)

                results.append(PromotionResult(
                    candidate_id=cand.candidate_id,
                    primitive_id=prim.id,
                    promoted=True,
                    reason="Promoted from experience",
                    old_status="CANDIDATE",
                    new_status="VERIFIED",
                ))
            except Exception as e:
                results.append(PromotionResult(
                    candidate_id=cand.candidate_id,
                    primitive_id=cand.primitive.id,
                    promoted=False,
                    reason=f"Failed: {e}",
                    old_status="CANDIDATE",
                    new_status="REJECTED",
                ))
                self._learner.reject_candidate(cand, str(e))

        self._results.extend(results)
        return results

    def get_results(self) -> list[PromotionResult]:
        return list(self._results)