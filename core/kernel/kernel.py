# core/kernel/kernel.py
"""Kernel — integrated agent kernel v1.0.

Integrates all subsystems:
    ProjectManager, ConfigManager, Planner, TaskEngine,
    Runtime, KnowledgeEngine, ExperienceEngine, EvaluationEngine

Loop:
    BOOTSTRAP → KNOWLEDGE_RETRIEVAL → REASONING → PLAN_VALIDATION
    → EXECUTION → OBSERVATION → VERIFICATION → EXPERIENCE
    → EVALUATION → LESSON → KNOWLEDGE_PROMOTION → IMPROVEMENT
    → COMPLETE

All loop steps are bounded by policy budgets.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from core.kernel.schema import KernelContext, KernelPhase, KernelStatus
from core.kernel.policy import PolicyEngine, Budget, Phase
from core.kernel.lifecycle import KernelLifecycle, _gen_run_id
from core.kernel.orchestrator import KernelOrchestrator
from core.kernel.evidence import KernelEvidence
from core.kernel.context import KernelContextBuilder


class KernelError(Exception):
    pass


@dataclass
class KernelResult:
    run_id: str
    goal: str
    status: str
    phase: str
    llm_calls: int
    estimated_tokens: int
    duration_seconds: float
    errors: list[str]

    @property
    def success(self) -> bool:
        return self.status == KernelStatus.COMPLETED.value


class Kernel:
    """Integrated Agent Kernel v1.0.

    Usage:
        kernel = Kernel()
        result = kernel.run(goal="analyze agent-core tests",
                           project_id="agent-core")
    """

    def __init__(self, project_id: Optional[str] = None,
                 budget: Optional[Budget] = None,
                 policy: Optional[PolicyEngine] = None):
        self._orchestrator = KernelOrchestrator(
            policy_engine=policy,
        )
        self._lifecycle = KernelLifecycle()
        self._evidence = KernelEvidence()
        self._ctx_builder = KernelContextBuilder()
        self._budget = budget or Budget()
        self._project_id = project_id or "agent-core"

    def run(self, goal: str, project_id: Optional[str] = None,
            resume_id: Optional[str] = None) -> KernelResult:
        """Execute the full kernel loop.

        Args:
            goal: the objective
            project_id: project to operate in
            resume_id: resume from existing run
        """
        t0 = time.time()
        pid = project_id or self._project_id

        # Bootstrap or resume
        if resume_id:
            ctx = self._lifecycle.resume(resume_id)
            if not ctx:
                raise KernelError(f"Run not found: {resume_id}")
            if ctx.kernel_status == KernelStatus.COMPLETED.value:
                return self._result_from_ctx(ctx, time.time() - t0)
        else:
            ctx = self._orchestrator.bootstrap(goal, pid)

        # Check budget
        if ctx.llm_calls >= self._budget.max_llm_calls:
            return self._fail(ctx, "LLM budget exhausted", t0)

        # Phase 1: Knowledge retrieval
        ctx = self._orchestrator.retrieve_knowledge(ctx)

        # Record evidence
        if ctx.knowledge_retrieved:
            self._evidence.record_knowledge_retrieval(
                ctx.goal, ctx.knowledge_retrieved, ctx.run_id
            )

        # Phase 2: Reasoning
        ctx = self._orchestrator.reason(ctx)

        # Phase 3: Plan validation
        ctx = self._orchestrator.validate_plan(ctx)

        # Phase 4: Execution (bounded)
        ctx = self._orchestrator.execute(ctx)

        # Phase 5: Observation
        ctx = self._orchestrator.observe(ctx)

        # Phase 6: Verification
        ctx = self._orchestrator.verify(ctx)

        # Phase 7: Experience recording
        ctx = self._orchestrator.record_experience(ctx)

        # Phase 8: Evaluation
        ctx = self._orchestrator.evaluate(ctx)

        # Phase 9: Lesson extraction
        ctx = self._orchestrator.extract_lesson(ctx)

        # Phase 10: Knowledge promotion
        ctx = self._orchestrator.promote_knowledge(ctx)

        # Phase 11: Improvement
        ctx = self._orchestrator.propose_improvement(ctx)

        # Mark complete
        ctx = self._lifecycle.mark_complete(ctx)
        return self._result_from_ctx(ctx, time.time() - t0)

    def resume(self, run_id: str) -> KernelResult:
        """Resume a previously started run."""
        return self.run(goal="", resume_id=run_id)

    def get_run(self, run_id: str) -> Optional[KernelContext]:
        return self._lifecycle.load(run_id)

    def list_runs(self) -> list[str]:
        return self._lifecycle.list_runs()

    def _result_from_ctx(self, ctx: KernelContext, elapsed: float) -> KernelResult:
        return KernelResult(
            run_id=ctx.run_id,
            goal=ctx.goal,
            status=ctx.kernel_status,
            phase=ctx.kernel_phase,
            llm_calls=ctx.llm_calls,
            estimated_tokens=ctx.estimated_tokens,
            duration_seconds=round(elapsed, 3),
            errors=list(ctx.errors),
        )

    def _fail(self, ctx: KernelContext, reason: str, t0: float) -> KernelResult:
        self._lifecycle.mark_failed(ctx, reason)
        return self._result_from_ctx(ctx, time.time() - t0)
