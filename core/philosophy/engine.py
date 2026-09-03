# core/philosophy/engine.py
"""Philosophy Engine — manages soft behavioral tendencies and human teaching feedback.

Architecture:
    Kernel / Security / Contracts > Verification requirements > Explicit task requirements > Philosophy

Philosophy represents soft tendencies derived from experience and human teaching.
It does NOT dictate execution, override safety invariants, or bypass verification.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Any

from core.experience.lesson import Lesson
from core.philosophy.schema import (
    PhilosophyStatus,
    TeachingType,
    EvolutionRecord,
    PhilosophyTendency,
)
from core.philosophy.store import PhilosophyStore, PhilosophyStoreError


class PhilosophyPrecedenceError(PermissionError):
    """Raised when philosophy attempts to override Kernel constraints or verification."""
    pass


class PhilosophyEngine:
    """Manages philosophy lifecycle, human teaching/challenge, and soft behavioral preferences."""

    def __init__(self, store: Optional[PhilosophyStore] = None):
        self._store = store or PhilosophyStore()
        self._next_id_seq = self._store.count() + 1

    def _gen_id(self) -> str:
        tid = f"PHIL-{self._next_id_seq:04d}"
        self._next_id_seq += 1
        return tid

    def _now_str(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── Experience -> Lesson -> Philosophy Candidate ─────────────────

    def propose_candidate_from_lesson(
        self,
        lesson: Lesson,
        statement: Optional[str] = None,
        initial_confidence: float = 0.3,
        tags: Optional[list[str]] = None,
    ) -> PhilosophyTendency:
        """Bridge a Lesson into a Philosophy Candidate.

        Preserves provenance back to lesson/experience IDs.
        Does NOT automatically activate the candidate.
        """
        stmt = statement or f"Tendency derived from lesson: {lesson.title}"
        origin = f"Lesson provenance: {lesson.lesson_id} (Source exp: {lesson.source_experience_id})"
        now = self._now_str()

        rec = EvolutionRecord(
            timestamp=now,
            from_status=PhilosophyStatus.CANDIDATE.value,
            to_status=PhilosophyStatus.CANDIDATE.value,
            reason=f"Candidate proposed from Lesson {lesson.lesson_id}",
            confidence_delta=initial_confidence,
            actor="lesson",
            action_type=TeachingType.TEACH.value,
        )

        tendency = PhilosophyTendency(
            tendency_id=self._gen_id(),
            statement=stmt,
            origin=origin,
            supporting_evidence_ids=[lesson.lesson_id],
            confidence=initial_confidence,
            status=PhilosophyStatus.CANDIDATE.value,
            created_at=now,
            updated_at=now,
            evolution_history=[rec],
            source_lesson_ids=[lesson.lesson_id],
            tags=tags or ["derived_from_lesson"],
        )

        self._store.save(tendency)
        return tendency

    # ── Human Teaching / Challenge Mechanisms ─────────────────────────

    def teach(
        self,
        statement: str,
        origin: str = "human_teaching",
        initial_confidence: float = 0.5,
        tags: Optional[list[str]] = None,
    ) -> PhilosophyTendency:
        """Teach the Agent a new behavioral tendency. Starts as candidate or supported based on confidence."""
        now = self._now_str()
        status = (
            PhilosophyStatus.SUPPORTED.value
            if initial_confidence >= 0.5
            else PhilosophyStatus.CANDIDATE.value
        )

        rec = EvolutionRecord(
            timestamp=now,
            from_status=PhilosophyStatus.CANDIDATE.value,
            to_status=status,
            reason="Human taught tendency",
            confidence_delta=initial_confidence,
            actor="human",
            action_type=TeachingType.TEACH.value,
        )

        tendency = PhilosophyTendency(
            tendency_id=self._gen_id(),
            statement=statement,
            origin=origin,
            confidence=initial_confidence,
            status=status,
            created_at=now,
            updated_at=now,
            evolution_history=[rec],
            tags=tags or ["human_taught"],
        )

        self._store.save(tendency)
        return tendency

    def support(
        self,
        tendency_id: str,
        feedback: str = "Human supported tendency",
        evidence_id: Optional[str] = None,
    ) -> PhilosophyTendency:
        """Human or experience supports a tendency, strengthening confidence and status."""
        t = self._must_get(tendency_id)
        old_status = t.status
        old_conf = t.confidence

        t.confidence = min(1.0, t.confidence + 0.2)
        if evidence_id and evidence_id not in t.supporting_evidence_ids:
            t.supporting_evidence_ids.append(evidence_id)

        # Transition candidate -> supported if confidence >= 0.4
        if t.status in (PhilosophyStatus.CANDIDATE.value, PhilosophyStatus.WEAKENED.value) and t.confidence >= 0.4:
            t.status = PhilosophyStatus.SUPPORTED.value

        now = self._now_str()
        rec = EvolutionRecord(
            timestamp=now,
            from_status=old_status,
            to_status=t.status,
            reason=feedback,
            confidence_delta=t.confidence - old_conf,
            actor="human",
            action_type=TeachingType.SUPPORT.value,
        )
        t.evolution_history.append(rec)
        t.updated_at = now
        self._store.save(t)
        return t

    def challenge(
        self,
        tendency_id: str,
        feedback: str = "Human challenged tendency",
        evidence_id: Optional[str] = None,
    ) -> PhilosophyTendency:
        """Human challenges a tendency, weakening confidence and status."""
        t = self._must_get(tendency_id)
        old_status = t.status
        old_conf = t.confidence

        t.confidence = max(0.0, t.confidence - 0.25)
        if evidence_id and evidence_id not in t.contradicting_evidence_ids:
            t.contradicting_evidence_ids.append(evidence_id)

        if t.confidence < 0.3 and t.status == PhilosophyStatus.SUPPORTED.value:
            t.status = PhilosophyStatus.WEAKENED.value

        now = self._now_str()
        rec = EvolutionRecord(
            timestamp=now,
            from_status=old_status,
            to_status=t.status,
            reason=feedback,
            confidence_delta=t.confidence - old_conf,
            actor="human",
            action_type=TeachingType.CHALLENGE.value,
        )
        t.evolution_history.append(rec)
        t.updated_at = now
        self._store.save(t)
        return t

    def contradict(
        self,
        tendency_id: str,
        feedback: str = "Contradictory evidence or human feedback",
        evidence_id: Optional[str] = None,
    ) -> PhilosophyTendency:
        """Contradict a tendency."""
        return self.challenge(tendency_id, feedback=feedback, evidence_id=evidence_id)

    def modify(
        self,
        tendency_id: str,
        new_statement: str,
        reason: str = "Human reshaped tendency statement",
    ) -> PhilosophyTendency:
        """Reshape/modify a philosophy tendency statement."""
        t = self._must_get(tendency_id)
        now = self._now_str()

        rec = EvolutionRecord(
            timestamp=now,
            from_status=t.status,
            to_status=t.status,
            reason=f"{reason}: '{t.statement}' -> '{new_statement}'",
            confidence_delta=0.0,
            actor="human",
            action_type=TeachingType.MODIFY.value,
        )
        t.statement = new_statement
        t.evolution_history.append(rec)
        t.updated_at = now
        self._store.save(t)
        return t

    def reject(
        self,
        tendency_id: str,
        reason: str = "Human rejected tendency",
    ) -> PhilosophyTendency:
        """Reject a tendency completely."""
        t = self._must_get(tendency_id)
        old_status = t.status
        old_conf = t.confidence

        t.status = PhilosophyStatus.REJECTED.value
        t.confidence = 0.0

        now = self._now_str()
        rec = EvolutionRecord(
            timestamp=now,
            from_status=old_status,
            to_status=PhilosophyStatus.REJECTED.value,
            reason=reason,
            confidence_delta=-old_conf,
            actor="human",
            action_type=TeachingType.REJECT.value,
        )
        t.evolution_history.append(rec)
        t.updated_at = now
        self._store.save(t)
        return t

    def retire(
        self,
        tendency_id: str,
        reason: str = "Human retired tendency",
    ) -> PhilosophyTendency:
        """Retire an obsolete tendency."""
        t = self._must_get(tendency_id)
        old_status = t.status
        old_conf = t.confidence

        t.status = PhilosophyStatus.RETIRED.value
        t.confidence = 0.0

        now = self._now_str()
        rec = EvolutionRecord(
            timestamp=now,
            from_status=old_status,
            to_status=PhilosophyStatus.RETIRED.value,
            reason=reason,
            confidence_delta=-old_conf,
            actor="human",
            action_type=TeachingType.RETIRE.value,
        )
        t.evolution_history.append(rec)
        t.updated_at = now
        self._store.save(t)
        return t

    # ── Soft Behavioral Preferences & Precedence Enforcement ──────────

    def consult_soft_preferences(
        self,
        task_context: Optional[dict] = None,
        min_confidence: float = 0.2,
    ) -> list[PhilosophyTendency]:
        """Consult philosophy tendencies as SOFT PREFERENCES for decision-making.

        Returns only active/supported tendencies sorted by confidence (highest first).
        """
        all_tendencies = self._store.list_all()
        active = [
            t for t in all_tendencies
            if t.is_active_preference() and t.confidence >= min_confidence
        ]
        active.sort(key=lambda x: x.confidence, reverse=True)
        return active

    def enforce_precedence_policy(
        self,
        requested_action: str,
        violates_kernel_invariant: bool = False,
        bypasses_verification: bool = False,
        violates_task_contract: bool = False,
    ) -> tuple[bool, str]:
        """Enforces absolute precedence:

        Kernel / Security / Contracts > Verification > Explicit task requirements > Philosophy

        Guarantees that Philosophy CANNOT override Kernel constraints, security boundaries,
        or verification requirements.
        """
        if violates_kernel_invariant:
            raise PhilosophyPrecedenceError(
                f"Philosophy cannot override Kernel invariant or security boundary: action={requested_action!r}"
            )
        if bypasses_verification:
            raise PhilosophyPrecedenceError(
                f"Philosophy cannot bypass verification requirements: action={requested_action!r}"
            )
        if violates_task_contract:
            raise PhilosophyPrecedenceError(
                f"Philosophy cannot override explicit task contract: action={requested_action!r}"
            )

        return True, "Precedence check passed: Philosophy operating within soft preference bounds."

    # ── Helpers ────────────────────────────────────────────────────────

    def _must_get(self, tendency_id: str) -> PhilosophyTendency:
        t = self._store.get(tendency_id)
        if not t:
            raise PhilosophyStoreError(f"Philosophy tendency not found: {tendency_id}")
        return t

    def get_tendency(self, tendency_id: str) -> Optional[PhilosophyTendency]:
        return self._store.get(tendency_id)

    def list_tendencies(
        self,
        status: Optional[str] = None,
    ) -> list[PhilosophyTendency]:
        all_t = self._store.list_all()
        if status:
            return [t for t in all_t if t.status == status]
        return all_t
