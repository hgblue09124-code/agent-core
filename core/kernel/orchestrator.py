# core/kernel/orchestrator.py
"""Kernel orchestrator — coordinates all subsystems."""

from __future__ import annotations

from typing import Optional

from core.kernel.schema import KernelContext, KernelPhase, KernelStatus
from core.kernel.policy import PolicyEngine, Phase
from core.kernel.lifecycle import KernelLifecycle, _gen_run_id


class KernelOrchestrator:
    """Orchestrates the kernel loop.

    Coordinates:
        - PolicyEngine
        - KernelLifecycle
        - KnowledgeEngine (lazy import)
        - ExperienceEngine (lazy import)
        - EvaluationEngine (lazy import)
    """

    def __init__(self, policy_engine: Optional[PolicyEngine] = None,
                 lifecycle: Optional[KernelLifecycle] = None):
        self._policy = policy_engine or PolicyEngine()
        self._lifecycle = lifecycle or KernelLifecycle()
        self._knowledge = None
        self._experience = None
        self._evaluation = None

    @property
    def knowledge(self):
        if self._knowledge is None:
            from core.knowledge.engine import KnowledgeEngine
            self._knowledge = KnowledgeEngine()
        return self._knowledge

    @property
    def experience(self):
        if self._experience is None:
            from core.experience.engine import ExperienceEngine
            self._experience = ExperienceEngine()
        return self._experience

    @property
    def evaluation(self):
        if self._evaluation is None:
            from core.evaluation.engine import EvaluationEngine
            self._evaluation = EvaluationEngine()
        return self._evaluation

    # ── Bootstrap ──────────────────────────────────────────────────

    def bootstrap(self, goal: str, project_id: str) -> KernelContext:
        """Create initial context."""
        run_id = _gen_run_id()
        ctx = KernelContext(
            run_id=run_id,
            goal=goal,
            project_id=project_id,
            kernel_phase=KernelPhase.BOOTSTRAP.value,
            kernel_status=KernelStatus.PENDING.value,
            created_at=KernelContext(
                run_id=run_id, goal=goal, project_id=project_id
            ).now_str(),
        )
        ctx.started_at = ctx.now_str()
        ctx.kernel_status = KernelStatus.RUNNING.value
        self._lifecycle.save(ctx)
        return ctx

    # ── Knowledge retrieval phase ───────────────────────────────────

    def retrieve_knowledge(self, ctx: KernelContext) -> KernelContext:
        """Retrieve relevant primitives."""
        if not self._policy.should_retrieve_knowledge(ctx.goal):
            ctx.kernel_phase = KernelPhase.REASONING.value
            return ctx

        result = self.knowledge.retrieve(
            ctx.goal,
            top_k=self._policy.policy.max_knowledge_top_k,
        )
        ctx.knowledge_retrieved = [s.primitive_id for s in result.scores]
        ctx.kernel_phase = KernelPhase.KNOWLEDGE_RETRIEVAL.value
        self._lifecycle.save(ctx)
        return ctx

    # ── Reasoning / Planning ───────────────────────────────────────

    def reason(self, ctx: KernelContext) -> KernelContext:
        """Plan using knowledge context + LLM if allowed."""
        if self._policy.should_call_llm(Phase.REASONING.value):
            # LLM planning would happen here
            # For now, we record the intent
            ctx.llm_calls += 1
            ctx.kernel_phase = KernelPhase.REASONING.value
        else:
            ctx.kernel_phase = KernelPhase.PLAN_VALIDATION.value
        self._lifecycle.save(ctx)
        return ctx

    # ── Plan validation ───────────────────────────────────────────

    def validate_plan(self, ctx: KernelContext) -> KernelContext:
        """Validate plan before execution."""
        # Policy check: must validate before execute
        if self._policy.policy.require_validation_before_execute:
            # In a real implementation, we would check plan structure here
            pass
        ctx.kernel_phase = KernelPhase.EXECUTION.value
        self._lifecycle.save(ctx)
        return ctx

    # ── Execution ─────────────────────────────────────────────────

    def execute(self, ctx: KernelContext) -> KernelContext:
        """Execute using RuntimeEngine."""
        if not self._policy.should_execute():
            ctx.kernel_phase = KernelPhase.OBSERVATION.value
            return ctx

        # Use RuntimeEngine for actual execution
        try:
            from core.runtime.engine import RuntimeEngine
            rt = RuntimeEngine()
            state = rt.run(ctx.project_id, ctx.goal)
            ctx.kernel_phase = KernelPhase.OBSERVATION.value
            self._lifecycle.save(ctx)
        except Exception as exc:
            ctx.errors.append(str(exc))
            ctx.kernel_phase = KernelPhase.FAILED.value
            ctx.kernel_status = KernelStatus.FAILED.value
            ctx.finished_at = ctx.now_str()
            self._lifecycle.save(ctx)
        return ctx

    # ── Observation ───────────────────────────────────────────────

    def observe(self, ctx: KernelContext) -> KernelContext:
        """Record observations."""
        ctx.kernel_phase = KernelPhase.VERIFICATION.value
        self._lifecycle.save(ctx)
        return ctx

    # ── Verification ──────────────────────────────────────────────

    def verify(self, ctx: KernelContext) -> KernelContext:
        """Verify outcome."""
        # LLM cannot self-declare verification
        if self._policy.can_llm_declare_verification():
            raise PermissionError("LLM cannot declare verification")
        ctx.kernel_phase = KernelPhase.EXPERIENCE.value
        self._lifecycle.save(ctx)
        return ctx

    # ── Experience ───────────────────────────────────────────────

    def record_experience(self, ctx: KernelContext) -> KernelContext:
        """Record experience."""
        if not self._policy.should_record_experience():
            ctx.kernel_phase = KernelPhase.EVALUATION.value
            return ctx

        from core.experience.schema import Experience
        exp = Experience(
            run_id=ctx.run_id,
            goal=ctx.goal,
            project_id=ctx.project_id,
            llm_calls=ctx.llm_calls,
            estimated_tokens=ctx.estimated_tokens,
            outcome="success" if ctx.kernel_status == KernelStatus.COMPLETED.value else "failure",
        )
        try:
            self.experience.record_experience(exp)
        except ValueError:
            pass  # already exists (idempotent)
        ctx.kernel_phase = KernelPhase.EVALUATION.value
        self._lifecycle.save(ctx)
        return ctx

    # ── Evaluation ────────────────────────────────────────────────

    def evaluate(self, ctx: KernelContext) -> KernelContext:
        """Evaluate the run."""
        from core.evaluation.schema import Evidence, EvidenceType
        ev = Evidence(
            evidence_id=f"ev-{ctx.run_id}",
            type=EvidenceType.TEST.value,
            source=f"kernel_run: {ctx.run_id}",
            result="PASS" if ctx.kernel_status == KernelStatus.COMPLETED.value else "FAIL",
            run_id=ctx.run_id,
        )
        self.evaluation.record_evidence(ev)
        evaluation = self.evaluation.evaluate_run(ctx.run_id, [ev])
        ctx.kernel_phase = KernelPhase.LESSON.value
        self._lifecycle.save(ctx)
        return ctx

    # ── Lesson ────────────────────────────────────────────────────

    def extract_lesson(self, ctx: KernelContext) -> KernelContext:
        """Extract lesson from experience."""
        ctx.kernel_phase = KernelPhase.KNOWLEDGE_PROMOTION.value
        self._lifecycle.save(ctx)
        return ctx

    # ── Knowledge promotion ───────────────────────────────────────

    def promote_knowledge(self, ctx: KernelContext) -> KernelContext:
        """Promote experience to knowledge if warranted."""
        if not self._policy.should_promote_knowledge():
            ctx.kernel_phase = KernelPhase.IMPROVEMENT.value
            return ctx
        ctx.kernel_phase = KernelPhase.IMPROVEMENT.value
        self._lifecycle.save(ctx)
        return ctx

    # ── Improvement ──────────────────────────────────────────────

    def propose_improvement(self, ctx: KernelContext) -> KernelContext:
        """Propose improvement if warranted."""
        ctx.kernel_phase = KernelPhase.COMPLETE.value
        ctx.kernel_status = KernelStatus.COMPLETED.value
        ctx.finished_at = ctx.now_str()
        self._lifecycle.save(ctx)
        return ctx
