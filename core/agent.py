# core/agent.py
"""Reference Agent — v0.2.0 composition point for Agent-Core.

Composition Architecture:
    - Agent-Core: Authority, identity, cognition, policy, orchestration, experience, learning, continuity.
    - agent-personal-vault: Persistent personal-data/storage layer (via PersonalVaultAdapter).
    - agent-capabilities: Replaceable capability adapters/dispatchers (via CapabilityRegistry & GitHubCapabilityAdapter).

Beta v0.1 Closed-Loop Architecture:
    Goal → Observe → Retrieve Personal Context → Reason → Plan → Decide Action →
    Authorize → Execute → Observe Result → Verify → Update Memory/Experience → Continue / Replan / Ask User / Complete

Precedence Hierarchy:
    Kernel / Security / Contracts > Verification requirements > Explicit task requirements > Learned strategies > Philosophy
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from core.context.pack import compact_tool_output
from core.kernel.kernel import Kernel, KernelResult
from core.kernel.policy import PolicyEngine, Budget
from core.projects.manager import ProjectManager
from core.philosophy.engine import PhilosophyEngine, PhilosophyPrecedenceError
from core.experience.engine import ExperienceEngine
from core.experience.schema import Experience
from core.experience.store import ExperienceStoreError
from core.memory.manager import MemoryManager
from core.memory.schema import MemoryItem, MemoryQuery, MemoryType
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
from core.runtime.loop import AgentLoopController, LoopStateStore
from core.runtime.state import AgentLoopState, AgentLoopStatus, AgentAction


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
    """Personal Agent — Core composition authority.

    Usage:
        agent = Agent(project_id="default")
        result = agent.run("Inspect system architecture")
    """

    VERSION = "0.2.0"

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

        self._loop_controller = AgentLoopController(
            project_id=self.project_id,
            agent=self,
            policy=self._policy,
            capabilities=self._capabilities,
            memory=self._memory,
            vault=self._vault,
            experience_engine=self._experience_engine,
            strategy_store=self._strategy_store,
            learning_pipeline=self._learning_pipeline,
            strategy_evaluator=self._strategy_evaluator,
            strategy_ranker=self._strategy_ranker,
            event_bus=self._event_bus,
            budget=self.budget,
            kernel=self._kernel,
        )
        self._loop_store = LoopStateStore()

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
        run_id: Optional[str] = None,
        project_id: Optional[str] = None,
        verbose: bool = False,
        capability_dispatch: Optional[tuple[str, dict[str, Any]]] = None,
        plan_actions: Optional[list[AgentAction]] = None,
        user_approved: bool = False,
        timeout_seconds: Optional[float] = None,
    ) -> AgentRunResult:
        """Execute a user task through the closed-loop Agent Loop runtime pipeline.

        Pipeline:
            OBSERVE → RETRIEVE PERSONAL CONTEXT → REASON → PLAN → DECIDE → AUTHORIZE →
            EXECUTE → OBSERVE RESULT → VERIFY → UPDATE MEMORY/EXPERIENCE → CONTINUE / REPLAN / ASK USER / COMPLETE
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

        # Enforce Philosophy precedence check
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

        loop_state, exp_recorded = self._loop_controller.run(
            goal=goal,
            run_id=run_id,
            project_id=pid,
            user_approved=user_approved,
            capability_dispatch=capability_dispatch,
            plan_actions=plan_actions,
            timeout_seconds=timeout_seconds,
        )

        elapsed = time.time() - t0

        # Map LoopState to AgentRunResult
        verdict = "FAIL"
        if loop_state.status == AgentLoopStatus.COMPLETED.value:
            verdict = "PASS"
        elif loop_state.status == AgentLoopStatus.WAITING_FOR_USER.value:
            verdict = "PENDING"

        obs_text = []
        for o in loop_state.observations:
            out = compact_tool_output(o.output) if o.output is not None else ""
            if isinstance(o.output, str) and "Capability '" in o.output:
                obs_text.append(compact_tool_output(o.output))
            else:
                obs_text.append(f"Observation ({o.action_id}): status={o.status}, output={out}")

        errors = [loop_state.error] if loop_state.error else []
        is_authorized = not (loop_state.status == AgentLoopStatus.FAILED.value and ("Policy DENY" in loop_state.error or "denied" in loop_state.error))

        return AgentRunResult(
            run_id=loop_state.run_id,
            project_id=loop_state.project_id,
            goal=loop_state.goal,
            status=loop_state.status,
            phase=loop_state.phase,
            plan_steps=loop_state.plan,
            authorized=is_authorized,
            verification_verdict=verdict,
            duration_seconds=elapsed,
            llm_calls=loop_state.telemetry.llm_calls,
            experience_recorded=exp_recorded,
            errors=errors,
            observations=obs_text,
        )

    # ── Continuation & Resumption ───────────────────────────────────────────

    def resume(self, run_id: str, user_approved: bool = True, timeout_seconds: Optional[float] = None) -> AgentRunResult:
        """Resume an interrupted or WAITING_FOR_USER task from checkpoint."""
        t0 = time.time()
        loop_state, exp_recorded = self._loop_controller.resume(run_id, user_approved=user_approved, timeout_seconds=timeout_seconds)
        elapsed = time.time() - t0

        verdict = "PASS" if loop_state.status == AgentLoopStatus.COMPLETED.value else ("PENDING" if loop_state.status == AgentLoopStatus.WAITING_FOR_USER.value else "FAIL")
        obs_text = [f"Resumed run '{run_id}'"]
        obs_text.extend([f"Observation ({o.action_id}): status={o.status}, output={o.output}" for o in loop_state.observations])

        return AgentRunResult(
            run_id=loop_state.run_id,
            project_id=loop_state.project_id,
            goal=loop_state.goal,
            status=loop_state.status,
            phase=loop_state.phase,
            plan_steps=loop_state.plan,
            authorized=True,
            verification_verdict=verdict,
            duration_seconds=elapsed,
            llm_calls=loop_state.telemetry.llm_calls,
            experience_recorded=exp_recorded,
            errors=[loop_state.error] if loop_state.error else [],
            observations=obs_text,
        )

    def cancel(self, run_id: str, reason: str = "User requested cancellation") -> AgentRunResult:
        """Cancel a running or paused task."""
        loop_state, _ = self._loop_controller.cancel(run_id, reason=reason)
        return AgentRunResult(
            run_id=loop_state.run_id,
            project_id=loop_state.project_id,
            goal=loop_state.goal,
            status=loop_state.status,
            phase=loop_state.phase,
            plan_steps=loop_state.plan,
            authorized=True,
            verification_verdict="FAIL",
            duration_seconds=0.0,
            llm_calls=0,
            experience_recorded=False,
            errors=[loop_state.error],
            observations=[],
        )

    def remember(
        self,
        content: str,
        memory_type: str = MemoryType.USER_CONTEXT.value,
        tags: Optional[list[str]] = None,
        importance: float = 0.8,
    ) -> MemoryItem:
        """Store a relevant personal fact. Does not inject it into every later prompt."""
        return self._memory.remember(
            content=content,
            memory_type=memory_type,
            tags=tags,
            importance=importance,
        )

    def retrieve_memory(self, query: str, limit: int = 5) -> list[MemoryItem]:
        """Relevance-gated memory retrieve."""
        return self._memory.retrieve(MemoryQuery(query=query, limit=limit))

    def forget(self, memory_id: str = "", query: str = "") -> bool:
        """Remove a memory by id or query. Identity cannot be forgotten this way."""
        return self._memory.forget(memory_id=memory_id, query=query)

    def inspect_run(self, run_id: str) -> Optional[dict]:
        """Inspect detailed lifecycle state of a run."""
        state = self._loop_store.load(run_id)
        if state:
            return state.to_dict()
        ctx = self._kernel.get_run(run_id)
        if ctx:
            return ctx.to_dict()
        return None

    def history(self) -> list[dict]:
        """List past runs history."""
        run_ids = self._kernel.list_runs()
        history_list = []
        for rid in reversed(run_ids):
            state = self._loop_store.load(rid)
            if state:
                history_list.append({
                    "run_id": state.run_id,
                    "goal": state.goal,
                    "project_id": state.project_id,
                    "status": state.status,
                    "phase": state.phase,
                    "started_at": state.started_at,
                    "finished_at": state.finished_at,
                })
            else:
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
