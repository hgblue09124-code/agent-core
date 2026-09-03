# core/knowledge/promotion.py
"""Knowledge promotion engine — evidence-based promotion through lifecycle.

Pipeline:
    Candidate → Validation → Verification → Promotion → ACTIVE

Rules:
    - CANDIDATE requires VALIDATED before it can become VERIFIED
    - VERIFIED requires evidence_count >= MIN_EVIDENCE_COUNT
    - ACTIVE requires confidence >= 0.5
    - Generated primitives can never auto-promote to ACTIVE
    - Every promotion must be recorded with evidence
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core.knowledge.lifecycle import Lifecycle, LifecycleError
from core.knowledge.schema import (
    Primitive, KnowledgeStatus, SourceType, Provenance, generate_primitive_id,
)
from core.knowledge.validator import KnowledgeValidator


MIN_EVIDENCE_FOR_ACTIVE = 2   # at least 2 evidence items
MIN_CONFIDENCE_FOR_ACTIVE = 0.5


@dataclass
class PromotionRecord:
    """A single promotion event."""
    record_id: str
    primitive_id: str
    from_status: str
    to_status: str
    reason: str
    evidence_ids: list[str] = field(default_factory=list)
    confidence_before: float = 0.0
    confidence_after: float = 0.0
    promoted_by: str = "agent-core"


class PromotionEngine:
    """Manages promotion through the knowledge lifecycle."""

    def __init__(self):
        self._lifecycle = Lifecycle()
        self._validator = KnowledgeValidator()
        self._records: list[PromotionRecord] = []

    def records(self) -> list[PromotionRecord]:
        return list(self._records)

    def can_promote(self, prim: Primitive, target_status: str) -> tuple[bool, str]:
        """Return (can_promote, reason)."""
        # Check lifecycle transition
        if not self._lifecycle.can_transition(prim.status, target_status):
            return False, f"Illegal lifecycle transition: {prim.status} → {target_status}"

        # Validation is required before VERIFIED
        if target_status == KnowledgeStatus.VERIFIED.value:
            report = self._validator.validate(prim)
            if not report.valid:
                return False, f"Validation failed: {[e.message for e in report.errors]}"

        # Evidence check for ACTIVE
        if target_status == KnowledgeStatus.ACTIVE.value:
            if prim.provenance.source_type == SourceType.GENERATED.value:
                return False, "Generated primitives cannot auto-promote to ACTIVE"

            evidence_count = len(prim.provenance.evidence_ids)
            if evidence_count < MIN_EVIDENCE_FOR_ACTIVE:
                return False, (
                    f"ACTIVE requires >= {MIN_EVIDENCE_FOR_ACTIVE} evidence items, "
                    f"got {evidence_count}"
                )

            if prim.confidence < MIN_CONFIDENCE_FOR_ACTIVE:
                return False, (
                    f"ACTIVE requires confidence >= {MIN_CONFIDENCE_FOR_ACTIVE}, "
                    f"got {prim.confidence}"
                )

        return True, "OK"

    def promote(self, prim: Primitive, target_status: str,
                reason: str, evidence_ids: Optional[list[str]] = None,
                promoted_by: str = "agent-core") -> tuple[Primitive, Optional[PromotionRecord]]:
        """Promote a primitive. Returns updated primitive and record, or raises."""
        can_do, why = self.can_promote(prim, target_status)
        if not can_do:
            raise LifecycleError(why)

        # Validate before VERIFIED/ACTIVE
        if target_status in (KnowledgeStatus.VERIFIED.value, KnowledgeStatus.ACTIVE.value):
            report = self._validator.validate(prim)
            if not report.valid:
                raise LifecycleError(f"Validation failed: {[e.message for e in report.errors]}")

        old_confidence = prim.confidence
        prim.status = target_status
        prim.updated_at = prim.now_str()

        # Add evidence IDs
        if evidence_ids:
            existing = set(prim.provenance.evidence_ids)
            existing.update(evidence_ids)
            prim.provenance.evidence_ids = list(existing)

        # Update confidence based on evidence count
        if target_status == KnowledgeStatus.ACTIVE.value:
            prim.confidence = min(1.0, prim.confidence + 0.1)

        record = PromotionRecord(
            record_id=generate_primitive_id("PROM"),
            primitive_id=prim.id,
            from_status=prim.status,
            to_status=target_status,
            reason=reason,
            evidence_ids=evidence_ids or [],
            confidence_before=old_confidence,
            confidence_after=prim.confidence,
            promoted_by=promoted_by,
        )
        self._records.append(record)
        return prim, record

    def record_observation(self, prim: Primitive, observation: str,
                           evidence_id: str) -> Primitive:
        """Record an observation against a primitive (increments evidence)."""
        prim = prim.__class__.from_dict(prim.to_dict())  # copy
        if evidence_id not in prim.provenance.evidence_ids:
            prim.provenance.evidence_ids.append(evidence_id)
        prim.updated_at = prim.now_str()
        return prim
