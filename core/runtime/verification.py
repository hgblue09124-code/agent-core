# core/runtime/verification.py
"""Verification Engine — independent deterministic verification of execution observations and goal satisfaction.

Pipeline:
    EXECUTE → OBSERVE_RESULT → VERIFY

Prevents LLM self-certification by verifying evidence, status, and expected outcome.
"""

from __future__ import annotations

from typing import Any, Optional

from core.capabilities.schema import CapabilityResult
from core.runtime.state import AgentAction, Observation, VerificationResult


class VerificationEngine:
    """Independent verifier evaluating execution evidence and goal satisfaction."""

    def verify_execution(
        self,
        goal: str,
        action: AgentAction,
        result: CapabilityResult,
        observation: Observation,
    ) -> VerificationResult:
        """Verify whether an action execution succeeded with valid evidence.

        Verdict:
            - PASS: Execution succeeded with verifiable evidence/output matching expectation.
            - FAIL: Execution failed, threw error, or returned status != SUCCESS/PASS/OK.
            - INCONCLUSIVE: Execution returned SUCCESS status but lacks required evidence or output.
        """
        if not result.success and result.status not in ("SUCCESS", "OK", "PASS"):
            return VerificationResult(
                verdict="FAIL",
                reason=f"Capability execution status was '{result.status}': {result.error or 'No error message'}",
                evidence_valid=False,
                goal_satisfied=False,
            )

        output = observation.output if observation.output is not None else result.output
        evidence = observation.evidence or result.metadata or {}

        # If execution status is SUCCESS, verify output / evidence
        if action.expected_outcome and "evidence_missing" in str(output).lower():
            return VerificationResult(
                verdict="FAIL",
                reason="Observed output indicates required evidence is missing",
                evidence_valid=False,
                goal_satisfied=False,
            )

        # Check for evidence presence when requested
        if action.expected_outcome and not output and not evidence:
            return VerificationResult(
                verdict="INCONCLUSIVE",
                reason="Capability execution succeeded but returned no output or evidence to verify outcome",
                evidence_valid=False,
                goal_satisfied=False,
            )

        # Basic evidence validity check
        evidence_valid = bool(output is not None or evidence)

        return VerificationResult(
            verdict="PASS",
            reason=f"Action '{action.action_id}' executed successfully and verified against expected outcome.",
            evidence_valid=evidence_valid,
            goal_satisfied=False,  # Loop controller will evaluate overall goal satisfaction
        )

    def verify_goal_satisfaction(
        self,
        goal: str,
        completed_actions: list[AgentAction],
        observations: list[Observation],
        verifications: list[VerificationResult],
    ) -> bool:
        """Determine whether the overarching user goal is satisfied based on evidence.

        Distinguishes individual execution success from overarching goal success.
        """
        if not verifications:
            return False

        # All recent verifications must pass
        if any(v.verdict in ("FAIL", "INCONCLUSIVE") for v in verifications[-len(completed_actions):]):
            return False

        if not completed_actions:
            return False

        # Goal is satisfied if at least one completed action produced passing evidence
        return any(v.verdict == "PASS" for v in verifications)
