# core/agent.py
"""Reference Agent — v0.1.0-beta developer-facing composition point for Agent-Core.

Composition Architecture:
    - Agent-Core: Authority, identity, cognition, policy, orchestration, experience, learning, continuity.
    - agent-personal-vault: Persistent personal-data/storage layer (via PersonalVaultAdapter).
    - agent-capabilities: Replaceable capability adapters/dispatchers (via CapabilityRegistry & GitHubCapabilityAdapter).

Beta v0.1 Acceptance Flow:
    User Request → Observe → Retrieve Personal Context → Reason → Plan → Policy/Authority
    → Capability Dispatch → Execute → Verify → Record Experience → Extract Lesson → Update Memory → Continue/Resume

Precedence Hierarchy:
    Kernel / Security / Contracts > Verification requirements > Explicit task requirements > Learned strategies > Philosophy
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from core.kernel.kernel import Kernel, KernelResult
from core.kernel.policy import PolicyEngine, Budget
from core.projects.manager import ProjectManager
from core.philosophy.engine import PhilosophyEngine, PhilosophyPrecedenceError
from core.experience.engine import ExperienceEngine
from core.experience.schema import Experience
from core.experience.store import ExperienceStoreError
from core.tasks.manager import TaskManager
from core.memory.manager import MemoryManager
from core.memory.schema import MemoryQuery, MemoryType
from core.capabilities.adapter import BaseCapabilityAdapter, CapabilityRegistry
from core.capabilities.mock_adapter import MockEchoCapabilityAdapter
from core.capabilities.github import GitHubCapabilityAdapter
from core.capabilities.schema import CapabilityResult, CapabilitySpec
from core.vault.adapter import BaseVaultAdapter, PersonalVaultAdapter
from core.learning.strategy import Strategy
from core.learning.store import StrategyStore
from core.learning.pipeline import LearningPipeline
from core.learning.evaluator import StrategyEvaluator
from core.learning.retrieval import StrategyRanker
from core.events.bus import EventBus
from core.events.schema import new_event, EventPhase, EventStatus


@dataclass
class AgentRunResult:
    """Developer-facing run result dataclass."""

    run_id: str
    project_id: str
    goal: str
    status: str
    phase: str
    plan_steps: list[str]
    authorized: bool
    verification_verdict: str
    duration_seconds: float
    llm_calls: int
    experience_recorded: bool
    errors: list[str] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.status == "COMPLETED" and self.verification_verdict == "PASS"

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "project_id": self.project_id,
            "goal": self.goal,
            "status": self.status,
            "phase": self.phase,
            "plan_steps": self.plan_steps,
            "authorized": self.authorized,
            "verification_verdict": self.verification_verdict,
            "duration_seconds": round(self.duration_seconds, 3),
            "llm_calls": self.llm_calls,
            "experience_recorded": self.experience_recorded,
            "errors": self.errors,
            "observations": self.observations,
        }


class Agent:
    """Personal Agent — Corecomposition authority.

    Usage:
        agent = Agent(project_id="default")
        result = agent.run("Inspect system architecture")
    """

    VERSION = "0.1.0-beta"

    def __init__(
        self,
        project_id: str = "default",
        provider: Optional[str] = None,
        budget: Optional[Budget] = None,
        vault: Optional[BaseVaultAdapter] = None,
    ):
        if provider:
            os.environ["AGENTCORE_PLANNER_PROVIDER"] = provider
        elif "AGENTCORE_PLANNER_PROVIDER" not in os.environ:
            os.environ["AGENTCORE_PLANNER_PROVIDER"] = "mock"

        self.project_id = project_id
        self.budget = budget or Budget()
        self._pm = ProjectManager()
        self._policy = PolicyEngine(budget=self.budget)
        self._philosophy = PhilosophyEngine()
        self._experience_engine = ExperienceEngine()
        self._memory = MemoryManager()
        self._vault = vault or PersonalVaultAdapter()
        self._capabilities = CapabilityRegistry()
        self._capabilities.register(MockEchoCapabilityAdapter())
        self._capabilities.register(GitHubCapabilityAdapter())
        self._strategy_store = StrategyStore()
        self._learning_pipeline = LearningPipeline(strategy_store=self._strategy_store)
        self._strategy_evaluator = StrategyEvaluator(store=self._strategy_store)
        self._strategy_ranker = StrategyRanker(store=self._strategy_store)
        self._event_bus = EventBus()
        self._kernel = Kernel(project_id=self.project_id, budget=self.budget, policy=self._policy)

    # ── Capability API ──────────────────────────────────────────────────────

    def register_capability(self, adapter: BaseCapabilityAdapter) -> None:
        """Register a new external capability adapter."""
        self._capabilities.register(adapter)

    def execute_capability(
        self,
        capability_id: str,
        inputs: dict[str, Any],
        user_approved: bool = False,
    ) -> CapabilityResult:
        """Execute a capability with strict policy/permission validation.

        Pipeline: Capability Lookup -> Policy Permission Check -> Capability Dispatch -> Result Observation
        """
        adapter = self._capabilities.get(capability_id)
        if not adapter:
            return CapabilityResult(
                capability_id=capability_id,
                status="FAILED",
                error=f"Capability '{capability_id}' not found in Core registry",
            )

        spec = adapter.get_spec()

        # Policy & Permission validation before execution
        authorized, reason = self._policy.authorize_capability(
            capability_spec=spec,
            action=inputs.get("action"),
            inputs=inputs,
            user_approved=user_approved,
        )

        if not authorized:
            return CapabilityResult(
                capability_id=capability_id,
                status="DENIED",
                error=f"Policy/Permission denial: {reason}",
            )

        # Dispatch execution safely through adapter
        result = self._capabilities.invoke(capability_id, inputs)

        # Record capability invocation as observable experience
        self._event_bus.publish(
            new_event(
                run_id="CAPABILITY-DISPATCH",
                phase=EventPhase.EXECUTE.value,
                action=f"Capability '{capability_id}' invoked: status={result.status}",
                status=EventStatus.OK.value if result.success else EventStatus.FAIL.value,
                metadata={"capability_id": capability_id, "result_status": result.status},
            )
        )

        return result

    # ── Orchestration Loop ──────────────────────────────────────────────────

    def run(
        self,
        goal: str,
        project_id: Optional[str] = None,
        verbose: bool = False,
        capability_dispatch: Optional[tuple[str, dict[str, Any]]] = None,
        user_approved: bool = False,
    ) -> AgentRunResult:
        """Execute a user task through the Personal Agent Beta v0.1 orchestration pipeline.

        Pipeline:
            OBSERVE → RETRIEVE PERSONAL CONTEXT → REASON → PLAN → POLICY → CAPABILITY DISPATCH → EXECUTE → VERIFY → RECORD EXPERIENCE → EXTRACT LESSON → UPDATE MEMORY → CONTINUE
        """
        t0 = time.time()
        pid = project_id or self.project_id

        # 1. TASK / OBSERVE: Verify project context
        if not self._pm.project_exists(pid):
            elapsed = time.time() - t0
            return AgentRunResult(
                run_id=f"ERR-{int(time.time()*1000):05d}",
                project_id=pid,
                goal=goal,
                status="FAILED",
                phase="TASK",
                plan_steps=[],
                authorized=False,
                verification_verdict="FAIL",
                duration_seconds=elapsed,
                llm_calls=0,
                experience_recorded=False,
                errors=[f"Project '{pid}' not found in registry"],
            )

        # 2. POLICY / AUTHORITY: PolicyEngine & Philosophy check
        if not self._policy.should_execute():
            elapsed = time.time() - t0
            return AgentRunResult(
                run_id=f"ERR-{int(time.time()*1000):05d}",
                project_id=pid,
                goal=goal,
                status="FAILED",
                phase="AUTHORITY",
                plan_steps=[],
                authorized=False,
                verification_verdict="FAIL",
                duration_seconds=elapsed,
                llm_calls=0,
                experience_recorded=False,
                errors=["Kernel policy prohibits execution"],
            )

        # Consult philosophy soft preferences (non-binding preferences)
        soft_prefs = self._philosophy.consult_soft_preferences(
            task_context={"project_id": pid, "goal": goal}
        )

        # Enforce strict precedence hierarchy: Kernel/Security > Verification > Task > Philosophy
        try:
            self._philosophy.enforce_precedence_policy(requested_action=goal)
        except PhilosophyPrecedenceError as exc:
            elapsed = time.time() - t0
            return AgentRunResult(
                run_id=f"ERR-{int(time.time()*1000):05d}",
                project_id=pid,
                goal=goal,
                status="FAILED",
                phase="AUTHORITY",
                plan_steps=[],
                authorized=False,
                verification_verdict="FAIL",
                duration_seconds=elapsed,
                llm_calls=0,
                experience_recorded=False,
                errors=[f"Authority violation: {exc}"],
            )

        # 3. RETRIEVE PERSONAL CONTEXT & MEMORY: Retrieve personal vault context, memory, and strategies
        identity_mem = self._memory.get_identity()
        relevant_mems = self._memory.retrieve(MemoryQuery(query=goal, limit=3))
        vault_contexts = self._vault.retrieve_context(query=goal, limit=3)
        applicable_strategies = self._strategy_ranker.select_applicable_strategies(goal=goal, limit=2)

        # Emit TASK_STARTED Event
        self._event_bus.publish(
            new_event(
                run_id=f"RUN-{int(t0*1000):05d}",
                phase=EventPhase.TASK_STARTED.value,
                action=f"Started run for goal '{goal}'",
            )
        )

        # 4. CAPABILITY DISPATCH (if requested)
        cap_observations = []
        cap_errors = []
        if capability_dispatch:
            cap_id, cap_inputs = capability_dispatch
            cap_res = self.execute_capability(cap_id, cap_inputs, user_approved=user_approved)
            if cap_res.success:
                cap_observations.append(f"Capability '{cap_id}' executed successfully: {cap_res.output}")
            elif cap_res.status == "DENIED":
                cap_errors.append(f"Capability '{cap_id}' denied: {cap_res.error}")
            else:
                cap_errors.append(f"Capability '{cap_id}' failed: {cap_res.error}")

        # Execute main kernel orchestration loop
        res: KernelResult = self._kernel.run(goal=goal, project_id=pid)
        ctx = self._kernel.get_run(res.run_id)

        # 5. OBSERVATIONS & PLAN STEPS
        plan_steps = []
        observations = [f"Identity: {identity_mem.content[:60]}..."]
        if vault_contexts:
            observations.extend([f"Vault personal context: {vc.get('data')}" for vc in vault_contexts])
        if relevant_mems:
            observations.extend([f"Memory context: {m.content[:50]}" for m in relevant_mems])
        if applicable_strategies:
            observations.extend([f"Applied strategy: {s.name} ({s.rule[:40]})" for s in applicable_strategies])
        if cap_observations:
            observations.extend(cap_observations)

        if ctx:
            if ctx.plan and hasattr(ctx.plan, "steps"):
                plan_steps = [f"{s.step_id}: {s.title}" for s in ctx.plan.steps]
            elif ctx.plan and isinstance(ctx.plan, dict):
                plan_steps = [
                    f"{s.get('step_id', '')}: {s.get('title', '')}"
                    for s in ctx.plan.get("steps", [])
                ]
            elif ctx.plan and isinstance(ctx.plan, str) and ctx.plan.strip():
                plan_steps = [ctx.plan.strip()]

            if ctx.knowledge_retrieved:
                observations.extend([f"Retrieved: {k}" for k in ctx.knowledge_retrieved[:3]])
            observations.append(f"Kernel phase: {ctx.kernel_phase}, status: {ctx.kernel_status}")

        if not plan_steps:
            tm = TaskManager()
            tasks = tm.list_tasks(project_id=pid)
            if tasks:
                plan_steps = [f"{t.task_id}: {t.title}" for t in tasks[:5]]

        # Combine errors
        run_errors = list(res.errors) if res.errors else []
        if cap_errors:
            run_errors.extend(cap_errors)

        # 6. RECORD EXPERIENCE
        exp_recorded = False
        exp = self._experience_engine.get_experience(res.run_id)
        if exp is not None:
            exp_recorded = True
        else:
            try:
                new_exp = Experience(
                    run_id=res.run_id,
                    goal=goal,
                    project_id=pid,
                    action=f"Agent.run('{goal}')",
                    observation=f"Kernel status={res.status}, phase={res.phase}",
                    outcome="success" if res.success and not cap_errors else "failure",
                    llm_calls=res.llm_calls,
                    estimated_tokens=res.estimated_tokens,
                )
                exp = self._experience_engine.record_experience(new_exp)
                exp_recorded = True
            except (ExperienceStoreError, ValueError, OSError, RuntimeError) as exc:
                exp_recorded = False
                run_errors.append(f"Experience recording failed: {exc}")

        # 7. EXTRACT LESSON -> FORM CANDIDATE STRATEGY -> EVALUATE STRATEGY
        if exp is not None:
            try:
                # Process experience into candidate strategy
                new_strat = self._learning_pipeline.process_experience(exp)

                # Evaluate applied strategies against verification result
                verdict = "PASS" if res.success and not cap_errors else "FAIL"
                for strat in applicable_strategies:
                    self._strategy_evaluator.evaluate_application(
                        strategy_id=strat.strategy_id,
                        run_id=res.run_id,
                        task_id=res.run_id,
                        verification_result=verdict,
                        actual_outcome=f"status={res.status}, phase={res.phase}",
                    )
            except (ExperienceStoreError, ValueError, OSError, RuntimeError) as exc:
                run_errors.append(f"Strategy learning pipeline notice: {exc}")
                self._event_bus.publish(
                    new_event(
                        run_id=res.run_id,
                        phase=EventPhase.EXPERIENCE.value,
                        action=f"Learning pipeline exception: {exc}",
                        status=EventStatus.FAIL.value,
                    )
                )

        # 8. UPDATE MEMORY & VAULT
        if res.success and not cap_errors:
            self._memory.remember(
                content=f"Successfully executed goal '{goal}' on project '{pid}'",
                memory_type=MemoryType.SHORT_TERM.value,
                source_run_id=res.run_id,
                importance=0.6,
            )
            # Store summary in vault if relevant
            self._vault.store_context(
                key=f"run_summary_{res.run_id}",
                data={"goal": goal, "run_id": res.run_id, "project_id": pid},
                category="run_history",
            )
            self._event_bus.publish(
                new_event(
                    run_id=res.run_id,
                    phase=EventPhase.MEMORY_UPDATED.value,
                    action=f"Remembered successful run '{res.run_id}'",
                    status=EventStatus.PASS.value,
                )
            )

        elapsed = time.time() - t0
        return AgentRunResult(
            run_id=res.run_id,
            project_id=pid,
            goal=goal,
            status=res.status if not cap_errors else ("FAILED" if res.success else res.status),
            phase=res.phase,
            plan_steps=plan_steps,
            authorized=True,
            verification_verdict="PASS" if (res.success and not cap_errors) else "FAIL",
            duration_seconds=elapsed,
            llm_calls=res.llm_calls,
            experience_recorded=exp_recorded,
            errors=run_errors,
            observations=observations,
        )

    # ── Continuation & Resumption ───────────────────────────────────────────

    def resume(self, run_id: str) -> AgentRunResult:
        """Resume an interrupted/non-terminal run from authoritative checkpoint."""
        t0 = time.time()
        res = self._kernel.resume(run_id)
        ctx = self._kernel.get_run(run_id)

        plan_steps = []
        if ctx and ctx.plan:
            if hasattr(ctx.plan, "steps"):
                plan_steps = [f"{s.step_id}: {s.title}" for s in ctx.plan.steps]
            elif isinstance(ctx.plan, dict):
                plan_steps = [f"{s.get('step_id', '')}: {s.get('title', '')}" for s in ctx.plan.get("steps", [])]

        elapsed = time.time() - t0
        return AgentRunResult(
            run_id=run_id,
            project_id=res.goal if hasattr(res, "project_id") else self.project_id,
            goal=res.goal,
            status=res.status,
            phase=res.phase,
            plan_steps=plan_steps,
            authorized=True,
            verification_verdict="PASS" if res.success else "FAIL",
            duration_seconds=elapsed,
            llm_calls=res.llm_calls,
            experience_recorded=True,
            errors=list(res.errors),
            observations=[f"Resumed run '{run_id}'"],
        )

    def inspect_run(self, run_id: str) -> Optional[dict]:
        """Inspect detailed lifecycle state of a run."""
        ctx = self._kernel.get_run(run_id)
        if not ctx:
            return None
        return ctx.to_dict()

    def history(self) -> list[dict]:
        """List past runs history."""
        run_ids = self._kernel.list_runs()
        history_list = []
        for rid in reversed(run_ids):
            ctx = self._kernel.get_run(rid)
            if ctx:
                history_list.append({
                    "run_id": ctx.run_id,
                    "goal": ctx.goal,
                    "project_id": ctx.project_id,
                    "status": ctx.kernel_status,
                    "phase": ctx.kernel_phase,
                    "started_at": ctx.started_at,
                    "finished_at": ctx.finished_at,
                })
        return history_list
