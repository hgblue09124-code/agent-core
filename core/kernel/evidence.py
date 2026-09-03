# core/kernel/evidence.py
"""Kernel evidence — records evidence from kernel execution."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from core.evaluation.schema import Evidence, EvidenceType, generate_eval_id


class KernelEvidence:
    """Records evidence from kernel-level operations.

    Each kernel operation records its evidence so the evaluation
    engine can build a full picture.
    """

    def __init__(self, ledger=None):
        self._ledger = ledger

    def record_knowledge_retrieval(self, query: str, retrieved_ids: list[str],
                                   run_id: str) -> Evidence:
        ev = Evidence(
            evidence_id=f"ev-kr-{run_id}",
            type=EvidenceType.COMMAND_RESULT.value,
            source=f"knowledge_retrieval: {query}",
            result=f"retrieved {len(retrieved_ids)} primitives",
            run_id=run_id,
        )
        return self._record(ev)

    def record_execution(self, task_id: str, result: str,
                        exit_code: int, run_id: str) -> Evidence:
        ev = Evidence(
            evidence_id=f"ev-ex-{run_id}-{task_id}",
            type=EvidenceType.COMMAND_RESULT.value,
            source=f"task_execution: {task_id}",
            result=result,
            run_id=run_id,
            task_id=task_id,
        )
        return self._record(ev)

    def record_verification(self, verified: bool, checks: list[str],
                           run_id: str) -> Evidence:
        ev = Evidence(
            evidence_id=f"ev-vf-{run_id}",
            type=EvidenceType.ASSERTION.value,
            source="verification",
            result="PASS" if verified else "FAIL",
            run_id=run_id,
        )
        return self._record(ev)

    def record_experience(self, experience_id: str,
                         success: bool, run_id: str) -> Evidence:
        ev = Evidence(
            evidence_id=f"ev-xp-{run_id}",
            type=EvidenceType.MANUAL.value,
            source=f"experience: {experience_id}",
            result="success" if success else "failure",
            run_id=run_id,
        )
        return self._record(ev)

    def record_evaluation(self, evaluation_id: str, verdict: str,
                         score: float, run_id: str) -> Evidence:
        ev = Evidence(
            evidence_id=f"ev-eval-{run_id}",
            type=EvidenceType.MANUAL.value,
            source=f"evaluation: {evaluation_id}",
            result=verdict,
            run_id=run_id,
        )
        return self._record(ev)

    def record_improvement(self, candidate_id: str, verdict: str,
                          run_id: str) -> Evidence:
        ev = Evidence(
            evidence_id=f"ev-imp-{run_id}",
            type=EvidenceType.MANUAL.value,
            source=f"improvement: {candidate_id}",
            result=verdict,
            run_id=run_id,
        )
        return self._record(ev)

    def _record(self, ev: Evidence) -> Evidence:
        if self._ledger:
            return self._ledger.record(ev)
        return ev
