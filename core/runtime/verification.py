# core/runtime/verification.py
"""Verification Engine — independent deterministic verification of execution observations and goal satisfaction.

Pipeline:
    EXECUTE → OBSERVE_RESULT → VERIFY

Prevents LLM self-certification by verifying evidence, status, and expected outcome.
Distinguishes individual ActionResult from overall GoalVerificationResult.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from core.capabilities.schema import CapabilityResult
from core.runtime.state import AgentAction, Observation, VerificationResult


@dataclass
class ActionResult:
    """Independent representation of an individual action execution result."""
    action_id: str
    success: bool
    status: str
    output: Any = None
    error: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class GoalVerificationResult:
    """Independent representation of overarching goal satisfaction evaluation."""
    goal_satisfied: bool
    reason: str
    evidence_summary: dict[str, Any] = field(default_factory=dict)


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

        # Check for evidence presence when requested
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

        # Strict outcome matching: If expected_outcome specifies key target terms, verify they match actual output/evidence
        if action.expected_outcome and output:
            output_str = str(output).lower()
            expected_lower = action.expected_outcome.lower()

            # Extract key expected tokens (excluding generic stop words)
            stop_words = {"a", "an", "the", "in", "on", "at", "for", "to", "of", "and", "or", "is", "be", "with", "that", "this", "by", "successful", "execution"}
            expected_tokens = [w for w in expected_lower.replace(":", " ").replace(",", " ").replace(".", " ").split() if w not in stop_words and len(w) > 2]

            # Check if explicit file / entity / identifier target mentioned in expected_outcome is contradicted in output
            if expected_tokens:
                matches = [tok for tok in expected_tokens if tok in output_str or any(tok in str(v).lower() for v in evidence.values())]
                if not matches and len(expected_tokens) >= 2:
                    return VerificationResult(
                        verdict="FAIL",
                        reason=f"Execution output does not match expected outcome targets: '{action.expected_outcome}'",
                        evidence_valid=False,
                        goal_satisfied=False,
                    )

        evidence_valid = bool(output is not None or evidence)

        return VerificationResult(
            verdict="PASS",
            reason=f"Action '{action.action_id}' executed successfully and verified against expected outcome.",
            evidence_valid=evidence_valid,
            goal_satisfied=False,
        )

    def evaluate_goal_verification(
        self,
        goal: str,
        completed_actions: list[AgentAction],
        observations: list[Observation],
        verifications: list[VerificationResult],
    ) -> GoalVerificationResult:
        """Evaluate overarching goal satisfaction based on evidence and action verifications.

        Action success != Goal success. Goal satisfaction requires valid observable evidence.
        """
        if not verifications or not completed_actions:
            return GoalVerificationResult(
                goal_satisfied=False,
                reason="No completed actions or verifications recorded for goal",
            )

        # Fail if any verification in completed actions failed or was inconclusive
        recent_verifs = verifications[-len(completed_actions):]
        if any(v.verdict in ("FAIL", "INCONCLUSIVE") for v in recent_verifs):
            return GoalVerificationResult(
                goal_satisfied=False,
                reason="Recent action verifications contain FAIL or INCONCLUSIVE verdicts",
            )

        # Check for evidence in observations
        valid_evidences = []
        for obs in observations:
            if obs.output and "evidence_missing" in str(obs.output).lower():
                return GoalVerificationResult(
                    goal_satisfied=False,
                    reason="Observable evidence is marked missing or incomplete",
                )
            if obs.output or obs.evidence:
                valid_evidences.append(obs.output or obs.evidence)

        if not valid_evidences:
            return GoalVerificationResult(
                goal_satisfied=False,
                reason="No verifiable evidence returned by completed actions",
            )

        return GoalVerificationResult(
            goal_satisfied=True,
            reason=f"Goal '{goal}' satisfied with {len(valid_evidences)} verified evidence outputs.",
            evidence_summary={"evidence_count": len(valid_evidences)},
        )

    def verify_goal_satisfaction(
        self,
        goal: str,
        completed_actions: list[AgentAction],
        observations: list[Observation],
        verifications: list[VerificationResult],
    ) -> bool:
        """Determine whether the overarching user goal is satisfied based on evidence."""
        res = self.evaluate_goal_verification(goal, completed_actions, observations, verifications)
        return res.goal_satisfied
