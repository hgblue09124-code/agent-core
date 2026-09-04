# core/kernel/policy.py
"""Kernel policy engine — deterministic decisions about subsystem usage.

All policies are explicit. No LLM decides.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Phase(str, Enum):
    BOOTSTRAP = "BOOTSTRAP"
    KNOWLEDGE_RETRIEVAL = "KNOWLEDGE_RETRIEVAL"
    REASONING = "REASONING"
    PLAN_VALIDATION = "PLAN_VALIDATION"
    RUNTIME_EXECUTION = "RUNTIME_EXECUTION"
    OBSERVATION = "OBSERVATION"
    VERIFICATION = "VERIFICATION"
    EXPERIENCE = "EXPERIENCE"
    EVALUATION = "EVALUATION"
    LESSON = "LESSON"
    KNOWLEDGE_PROMOTION = "KNOWLEDGE_PROMOTION"
    IMPROVEMENT_CANDIDATE = "IMPROVEMENT_CANDIDATE"
    EVIDENCE = "EVIDENCE"
    COMPLETE = "COMPLETE"


@dataclass
class Budget:
    """Runtime budget for one kernel run."""
    max_runtime_seconds: float = 600.0
    max_llm_calls: int = 20
    max_token_budget: int = 20000
    max_retries: int = 2
    max_knowledge_retrieval: int = 5
    max_evaluation_cycles: int = 3


@dataclass
class Policy:
    """Static policy configuration."""
    # When to retrieve knowledge
    retrieve_knowledge_if_goal: bool = True
    max_knowledge_top_k: int = 5

    # When to call LLM
    use_llm_for_planning: bool = True
    use_llm_for_diagnosis: bool = True
    use_llm_for_lesson: bool = False  # default deterministic

    # When to execute
    auto_execute: bool = True
    require_validation_before_execute: bool = True

    # When to retry
    retry_on_transient_failure: bool = True
    retry_on_test_failure: bool = True

    # When to replan
    replan_on_unknown_failure: bool = True
    replan_on_logic_failure: bool = True

    # When to record experience
    always_record_experience: bool = True

    # When to promote knowledge
    promote_only_with_evidence: bool = True

    # When to propose improvement
    propose_improvement_on_regression: bool = True

    # When to accept improvement
    auto_accept_improvement: bool = False   # explicit acceptance only

    # LLM boundary
    llm_can_declare_verification: bool = False
    llm_can_promote_knowledge: bool = False
    llm_can_accept_improvement: bool = False
    llm_can_bypass_validator: bool = False


class PolicyEngine:
    """Answers policy questions deterministically."""

    def __init__(self, policy: Optional[Policy] = None, budget: Optional[Budget] = None):
        self.policy = policy or Policy()
        self.budget = budget or Budget()

    # ── Knowledge retrieval ──────────────────────────────────────────

    def should_retrieve_knowledge(self, goal: str) -> bool:
        """Should we retrieve knowledge for this goal?"""
        if not self.policy.retrieve_knowledge_if_goal:
            return False
        if len(goal.strip()) < 3:
            return False
        return True

    # ── LLM use ──────────────────────────────────────────────────────

    def should_call_llm(self, phase: str) -> bool:
        """Should we call the LLM for this phase?"""
        if phase == Phase.REASONING.value:
            return self.policy.use_llm_for_planning
        if phase == Phase.OBSERVATION.value:
            return self.policy.use_llm_for_diagnosis
        if phase == Phase.LESSON.value:
            return self.policy.use_llm_for_lesson
        return False

    # ── Execute / retry / replan ─────────────────────────────────────

    def should_execute(self) -> bool:
        return self.policy.auto_execute

    def should_retry(self, attempt: int) -> bool:
        return (
            self.policy.retry_on_transient_failure
            and attempt < self.budget.max_retries
        )

    def should_replan(self, failure_category: str) -> bool:
        if failure_category in ("UNKNOWN", "LOGIC"):
            return self.policy.replan_on_logic_failure
        if failure_category == "LOGIC":
            return self.policy.replan_on_logic_failure
        return self.policy.replan_on_unknown_failure

    # ── Experience / Promotion / Improvement ─────────────────────────

    def should_record_experience(self) -> bool:
        return self.policy.always_record_experience

    def should_promote_knowledge(self) -> bool:
        return self.policy.promote_only_with_evidence

    def should_propose_improvement(self) -> bool:
        return self.policy.propose_improvement_on_regression

    def should_auto_accept_improvement(self) -> bool:
        return self.policy.auto_accept_improvement

    # ── LLM boundary checks ─────────────────────────────────────────

    def can_llm_declare_verification(self) -> bool:
        return self.policy.llm_can_declare_verification

    def can_llm_promote_knowledge(self) -> bool:
        return self.policy.llm_can_promote_knowledge

    def can_llm_accept_improvement(self) -> bool:
        return self.policy.llm_can_accept_improvement

    def can_llm_bypass_validator(self) -> bool:
        return self.policy.llm_can_bypass_validator

    # ── Capability Authorization ────────────────────────────────────

    def authorize_capability(
        self,
        capability_spec: Any,
        action: Optional[str] = None,
        inputs: Optional[dict] = None,
        user_approved: bool = False,
    ) -> tuple[bool, Optional[str]]:
        """Validate whether capability execution is permitted under current policy & constraints.

        Returns (authorized: bool, reason: Optional[str]).
        """
        if not self.should_execute():
            return False, "Policy prohibits overall execution"

        constraints = getattr(capability_spec, "constraints", None)
        act_str = str(action or (inputs or {}).get("action", "")).lower()
        write_keywords = ("create", "update", "delete", "post", "put", "patch", "write", "comment")
        is_write_action = any(kw in act_str for kw in write_keywords)

        if constraints:
            # Read-only constraint check
            read_only = getattr(constraints, "read_only", False)
            if read_only and is_write_action:
                return False, f"Capability '{getattr(capability_spec, 'capability_id', 'unknown')}' is restricted to read-only actions (requested: '{act_str}')"

            # Write actions or capabilities marked requires_user_approval demand explicit approval
            req_approval = getattr(constraints, "requires_user_approval", False) or is_write_action
            if req_approval and not user_approved:
                return False, f"Action '{act_str}' on capability '{getattr(capability_spec, 'capability_id', 'unknown')}' requires explicit user approval"

            # Domain restriction check
            allowed_domains = getattr(constraints, "allowed_domains", [])
            target_domain = (inputs or {}).get("domain") or (inputs or {}).get("url")
            if allowed_domains and target_domain:
                if not any(dom in str(target_domain) for dom in allowed_domains):
                    return False, f"Target domain '{target_domain}' is not in allowed domains list {allowed_domains}"

        return True, None
