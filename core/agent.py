# core/agent.py
"""Reference Agent — v0.1.0-beta developer-facing runtime for Agent-Core.

Orchestration Pipeline:
    Task → Plan → Authority → Execution → Observation → Verification → Result → Experience

Precedence Hierarchy:
    Kernel / Security / Contracts > Verification requirements > Explicit task requirements > Philosophy / behavioral tendencies
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Optional

from core.kernel.kernel import Kernel, KernelResult
from core.kernel.policy import PolicyEngine, Budget
from core.projects.manager import ProjectManager
from core.philosophy.engine import PhilosophyEngine
from core.experience.engine import ExperienceEngine
from core.experience.schema import Experience
from core.tasks.manager import TaskManager


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
    """Reference Agent — developer-facing preview runtime.

    Usage:
        agent = Agent(project_id="default")
        result = agent.run("Inspect the project architecture")
    """

    VERSION = "0.1.0-beta"

    def __init__(
        self,
        project_id: str = "default",
        provider: Optional[str] = None,
        budget: Optional[Budget] = None,
    ):
        if provider:
            os.environ["AGENTCORE_PLANNER_PROVIDER"] = provider
        elif "AGENTCORE_PLANNER_PROVIDER" not in os.environ:
            os.environ["AGENTCORE_PLANNER_PROVIDER"] = "mock"

        self.project_id = project_id
        self.budget = budget or Budget()
        self._pm = ProjectManager()
        self._policy = PolicyEngine()
        self._philosophy = PhilosophyEngine()
        self._experience_engine = ExperienceEngine()
        self._kernel = Kernel(project_id=self.project_id, budget=self.budget)

    def run(
        self,
        goal: str,
        project_id: Optional[str] = None,
        verbose: bool = False,
    ) -> AgentRunResult:
        """Execute a user task through the reference Agent orchestration pipeline.

        Pipeline:
            TASK -> PLAN -> AUTHORITY -> EXECUTION -> OBSERVATION -> VERIFICATION -> RESULT -> EXPERIENCE
        """
        t0 = time.time()
        pid = project_id or self.project_id

        # 1. TASK: Verify project context
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

        # 2. AUTHORITY: PolicyEngine check
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
        except Exception as exc:
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

        # Execute through Kernel Orchestrator Loop
        res: KernelResult = self._kernel.run(goal=goal, project_id=pid)
        ctx = self._kernel.get_run(res.run_id)

        # Extract observations & plan steps
        plan_steps = []
        observations = []
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

        if not plan_steps:
            tm = TaskManager()
            tasks = tm.list_tasks(project_id=pid)
            if tasks:
                plan_steps = [f"{t.task_id}: {t.title}" for t in tasks[:5]]

        # Record Experience / Verify Experience Persistence
        exp_recorded = False
        run_errors = list(res.errors) if res.errors else []
        if self._experience_engine.get_experience(res.run_id) is not None:
            exp_recorded = True
        else:
            try:
                exp = Experience(
                    run_id=res.run_id,
                    goal=goal,
                    project_id=pid,
                    action=f"Agent.run('{goal}')",
                    observation=f"Kernel status={res.status}, phase={res.phase}",
                    outcome="success" if res.success else "failure",
                    llm_calls=res.llm_calls,
                    estimated_tokens=res.estimated_tokens,
                )
                self._experience_engine.record_experience(exp)
                exp_recorded = True
            except Exception as exc:
                exp_recorded = False
                run_errors.append(f"Experience recording failed: {exc}")

        elapsed = time.time() - t0
        return AgentRunResult(
            run_id=res.run_id,
            project_id=pid,
            goal=goal,
            status=res.status,
            phase=res.phase,
            plan_steps=plan_steps,
            authorized=True,
            verification_verdict="PASS" if res.success else "FAIL",
            duration_seconds=elapsed,
            llm_calls=res.llm_calls,
            experience_recorded=exp_recorded,
            errors=run_errors,
            observations=observations,
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
