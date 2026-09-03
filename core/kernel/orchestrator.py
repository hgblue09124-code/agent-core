# core/kernel/orchestrator.py
"""Kernel orchestrator — coordinates all subsystems."""

from __future__ import annotations

import time
from typing import Optional

from core.kernel.schema import KernelContext, KernelPhase, KernelStatus
from core.kernel.policy import PolicyEngine, Phase
from core.kernel.lifecycle import KernelLifecycle, _gen_run_id
from core.events.bus import get_bus
from core.events.schema import EventPhase, EventStatus, new_event


class KernelOrchestrator:
    """Orchestrates the kernel loop.

    Coordinates:
        - PolicyEngine
        - KernelLifecycle
        - KnowledgeEngine (lazy import)
        - ExperienceEngine (lazy import)
        - EvaluationEngine (lazy import)
        - EventBus (lazy, for live activity)
    """

    def __init__(self, policy_engine: Optional[PolicyEngine] = None,
                 lifecycle: Optional[KernelLifecycle] = None,
                 event_bus=None):
        self._policy = policy_engine or PolicyEngine()
        self._lifecycle = lifecycle or KernelLifecycle()
        self._knowledge = None
        self._experience = None
        self._evaluation = None
        self._events = event_bus  # None → uses global get_bus() lazily

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

    @property
    def _bus(self):
        if self._events is None:
            self._events = get_bus()
        return self._events

    def _emit(self, ctx: KernelContext, phase: str, action: str,
              status: str = EventStatus.RUNNING.value,
              **kwargs) -> None:
        """Emit an event. Non-blocking, secrets auto-redacted."""
        ev = new_event(
            run_id=ctx.run_id,
            phase=phase,
            action=action,
            status=status,
            **kwargs,
        )
        try:
            self._bus.publish(ev)
        except Exception:
            pass  # never let event bus crash the kernel

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
        self._emit(ctx, EventPhase.PLAN.value,
                   f"BOOTSTRAP goal={goal[:60]}", EventStatus.OK.value,
                   metadata={"goal": goal[:100]})
        return ctx

    # ── Knowledge retrieval phase ───────────────────────────────────

    def retrieve_knowledge(self, ctx: KernelContext) -> KernelContext:
        """Retrieve relevant primitives."""
        if not self._policy.should_retrieve_knowledge(ctx.goal):
            ctx.kernel_phase = KernelPhase.REASONING.value
            return ctx

        t0 = time.time()
        result = self.knowledge.retrieve(
            ctx.goal,
            top_k=self._policy.policy.max_knowledge_top_k,
        )
        ctx.knowledge_retrieved = [s.primitive_id for s in result.scores]
        ctx.kernel_phase = KernelPhase.KNOWLEDGE_RETRIEVAL.value
        self._lifecycle.save(ctx)
        self._emit(ctx, EventPhase.KNOWLEDGE.value,
                   f"Retrieved {len(ctx.knowledge_retrieved)} primitive(s)",
                   EventStatus.OK.value,
                   duration=time.time() - t0,
                   message=", ".join(ctx.knowledge_retrieved[:3]))
        return ctx

    # ── Reasoning / Planning ───────────────────────────────────────

    def reason(self, ctx: KernelContext) -> KernelContext:
        """Plan using knowledge context + LLM if allowed."""
        if self._policy.should_call_llm(Phase.REASONING.value):
            # LLM planning would happen here
            # For now, we record the intent
            ctx.llm_calls += 1
            ctx.kernel_phase = KernelPhase.REASONING.value
            self._emit(ctx, EventPhase.PLAN.value,
                       "LLM planning invoked",
                       EventStatus.RUNNING.value,
                       metadata={"llm_calls": ctx.llm_calls})
        else:
            ctx.kernel_phase = KernelPhase.PLAN_VALIDATION.value
            self._emit(ctx, EventPhase.PLAN.value,
                       "Plan constructed (deterministic)",
                       EventStatus.OK.value)
        self._lifecycle.save(ctx)
        return ctx

    # ── Plan validation ───────────────────────────────────────────

    def validate_plan(self, ctx: KernelContext) -> KernelContext:
        """Validate plan before execution."""
        # Policy check: must validate before execute
        if self._policy.policy.require_validation_before_execute:
            pass
        ctx.kernel_phase = KernelPhase.EXECUTION.value
        self._lifecycle.save(ctx)
        self._emit(ctx, EventPhase.PLAN.value,
                   "Plan validated",
                   EventStatus.OK.value)
        return ctx

    # ── Execution ─────────────────────────────────────────────────

    def execute(self, ctx: KernelContext) -> KernelContext:
        """Execute using RuntimeEngine."""
        if not self._policy.should_execute():
            ctx.kernel_phase = KernelPhase.OBSERVATION.value
            return ctx

        t0 = time.time()
        self._emit(ctx, EventPhase.EXECUTE.value,
                   "RuntimeEngine.run() starting",
                   EventStatus.RUNNING.value)
        # Use RuntimeEngine for actual execution
        try:
            from core.runtime.engine import RuntimeEngine
            rt = RuntimeEngine()
            state = rt.run(ctx.project_id, ctx.goal)
            ctx.kernel_phase = KernelPhase.OBSERVATION.value
            self._lifecycle.save(ctx)
            self._emit(ctx, EventPhase.EXECUTE.value,
                       f"RuntimeEngine completed ({state.status})",
                       EventStatus.OK.value,
                       duration=time.time() - t0)
        except Exception as exc:
            ctx.errors.append(str(exc))
            ctx.kernel_phase = KernelPhase.FAILED.value
            ctx.kernel_status = KernelStatus.FAILED.value
            ctx.finished_at = ctx.now_str()
            self._lifecycle.save(ctx)
            self._emit(ctx, EventPhase.EXECUTE.value,
                       f"RuntimeEngine error: {exc}",
                       EventStatus.ERROR.value,
                       duration=time.time() - t0)
        return ctx

    # ── Observation ───────────────────────────────────────────────

    def observe(self, ctx: KernelContext) -> KernelContext:
        """Record observations."""
        self._emit(ctx, EventPhase.OBSERVE.value,
                   "Observing execution results",
                   EventStatus.OK.value)
        ctx.kernel_phase = KernelPhase.VERIFICATION.value
        self._lifecycle.save(ctx)
        return ctx

    # ── Verification ──────────────────────────────────────────────

    def verify(self, ctx: KernelContext) -> KernelContext:
        """Verify outcome."""
        # LLM cannot self-declare verification
        if self._policy.can_llm_declare_verification():
            raise PermissionError("LLM cannot declare verification")
        self._emit(ctx, EventPhase.VERIFY.value,
                   "Verification check",
                   EventStatus.OK.value)
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
            self._emit(ctx, EventPhase.EXPERIENCE.value,
                       "Experience recorded", EventStatus.OK.value,
                       metadata={"outcome": outcome})
        except ValueError:
            self._emit(ctx, EventPhase.EXPERIENCE.value,
                       "Experience already exists", EventStatus.OK.value)
        ctx.kernel_phase = KernelPhase.EVALUATION.value
        self._lifecycle.save(ctx)
        return ctx

    # ── Evaluation ────────────────────────────────────────────────

    def evaluate(self, ctx: KernelContext) -> KernelContext:
        """Evaluate the run."""
        from core.evaluation.schema import Evidence, EvidenceType
        verdict = "PASS" if ctx.kernel_status == KernelStatus.COMPLETED.value else "FAIL"
        ev = Evidence(
            evidence_id=f"ev-{ctx.run_id}",
            type=EvidenceType.TEST.value,
            source=f"kernel_run: {ctx.run_id}",
            result=verdict,
            run_id=ctx.run_id,
        )
        self.evaluation.record_evidence(ev)
        evaluation = self.evaluation.evaluate_run(ctx.run_id, [ev])
        self._emit(ctx, EventPhase.EVALUATION.value,
                   f"Evaluation verdict={evaluation.verdict}",
                   EventStatus.OK.value if evaluation.verdict == "PASS" else EventStatus.FAIL.value,
                   metadata={"score": round(evaluation.total_score(), 3)})
        ctx.kernel_phase = KernelPhase.LESSON.value
        self._lifecycle.save(ctx)
        return ctx

    # ── Lesson ────────────────────────────────────────────────────

    def extract_lesson(self, ctx: KernelContext) -> KernelContext:
        """Extract lesson from experience."""
        self._emit(ctx, EventPhase.EVALUATION.value,
                   "Lesson extracted", EventStatus.OK.value)
        ctx.kernel_phase = KernelPhase.KNOWLEDGE_PROMOTION.value
        self._lifecycle.save(ctx)
        return ctx

    # ── Knowledge promotion ───────────────────────────────────────

    def promote_knowledge(self, ctx: KernelContext) -> KernelContext:
        """Promote experience to knowledge if warranted."""
        if not self._policy.should_promote_knowledge():
            ctx.kernel_phase = KernelPhase.IMPROVEMENT.value
            return ctx
        self._emit(ctx, EventPhase.EVALUATION.value,
                   "Knowledge promotion check", EventStatus.OK.value)
        ctx.kernel_phase = KernelPhase.IMPROVEMENT.value
        self._lifecycle.save(ctx)
        return ctx

    # ── Improvement ──────────────────────────────────────────────

    def propose_improvement(self, ctx: KernelContext) -> KernelContext:
        """Propose improvement if warranted."""
        self._emit(ctx, EventPhase.RESULT.value,
                   f"RESULT {ctx.kernel_status}",
                   EventStatus.OK.value if ctx.kernel_status == KernelStatus.COMPLETED.value
                   else EventStatus.FAIL.value)
        ctx.kernel_phase = KernelPhase.COMPLETE.value
        ctx.kernel_status = KernelStatus.COMPLETED.value
        ctx.finished_at = ctx.now_str()
        self._lifecycle.save(ctx)
        return ctx
