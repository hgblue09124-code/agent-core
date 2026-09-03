# core/runtime/engine.py
"""Runtime v0.6 — autonomous execution engine.

Pipeline:
    Bootstrap → Plan → Refine → Validate → Execute → Observe → Verify
    → Checkpoint → (Next Task | Recover | Stop)

Design:
    - LLM = PLANNER  (never executes)
    - TaskRunner = EXECUTOR  (deterministic)
    - Runtime = ORCHESTRATOR  (stateful, checkpoint-aware)
    - Budget limits enforced locally; LLM escalation is selective

Secrets:
    API keys stay in ConfigManager. Never logged or persisted.
"""

from __future__ import annotations

import copy
import re
import sys
import time
from pathlib import Path
from typing import Optional

# agent-core paths
_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.config.manager import ConfigManager
from core.planner.schema import Plan, PlanStep, ValidationResult, ValidationError
from core.planner.validator import validate_plan
from core.planner.planner import Planner, PlanResult, plan_to_task
from core.planner.prompt import PromptConfig
from core.tasks.manager import TaskManager
from core.tasks.runner import TaskRunner
from core.tasks.schema import Task, TaskStep, StepType, TaskStatus
from core.projects.manager import ProjectManager
from core.runtime.schema import RunState, RunStatus, RunPhase, PhaseMetrics
from core.runtime.checkpoint import CheckpointStore
from core.runtime.config import RuntimeConfig


# ── Diagnostic helpers ───────────────────────────────────────────────────

_URL_RE = re.compile(r"^https?://")


def _diagnose_failure(error: str, step: TaskStep,
                      step_result: Optional[dict] = None) -> tuple[str, bool]:
    """Simple deterministic failure diagnosis.

    Returns (diagnosis, can_recover_locally).
    Local recovery = we can fix this without LLM help.
    """
    err_lower = error.lower()

    # Syntax / obvious typos
    if "syntaxerror" in err_lower or "nameerror" in err_lower:
        return "CODE_ERROR: syntax/name error — may be fixable locally", True
    if "indentationerror" in err_lower:
        return "CODE_ERROR: indentation issue", True
    if "filenotfounderror" in err_lower or "no such file" in err_lower:
        return "FILE_ERROR: missing file or path", True
    if "permission denied" in err_lower:
        return "PERMISSION_ERROR: access denied", False
    if "connection refused" in err_lower:
        return "NETWORK_ERROR: service unreachable — requires attention", False

    # Command-not-found style errors
    if "command not found" in err_lower or "not found" in err_lower:
        if step.type == StepType.SHELL:
            cmd = step.command if step.command else (step.args[0] if step.args else "")
            if "/" not in cmd and cmd not in ("cd", "ls", "cat", "grep", "sed", "awk",
                                               "python", "python3", "node", "npm",
                                               "pnpm", "git", "make", "gcc", "go"):
                return f"COMMAND_ERROR: unknown command '{cmd}'", False
        return "COMMAND_ERROR: command unavailable", False

    # Exit code non-zero without clear error text — requires observation
    if step_result and step_result.get("exit_code", 0) != 0 and not error:
        return f"EXIT_CODE_{step_result['exit_code']}: non-zero exit — needs inspection", False

    # Unknown — escalate
    return f"UNKNOWN_ERROR: {error[:100]}", False


# ── Runtime Engine ────────────────────────────────────────────────────────

class RuntimeEngine:
    """Stateful autonomous runtime with durable checkpoints.

    This is the core loop. It orchestrates Planner → TaskManager →
    TaskRunner while tracking state, budgets, and checkpoints.
    """

    def __init__(
        self,
        runs_dir: Optional[str] = None,
        config: Optional[RuntimeConfig] = None,
    ):
        self._store = CheckpointStore(runs_dir)
        self._cfg = config or RuntimeConfig.from_env()
        self._pm = ProjectManager()
        self._tm = TaskManager()
        self._tr = TaskRunner()
        self._config_manager = ConfigManager()

        # LLM planner (lazy — only created when first LLM call needed)
        self._planner: Optional[Planner] = None
        self._current_state: Optional[RunState] = None

    # ── Planner access ───────────────────────────────────────────────

    def _get_planner(self) -> Planner:
        if self._planner is None:
            from core.planner.planner import create_provider
            provider = create_provider()
            self._planner = Planner(provider=provider)
        return self._planner

    # ── Budget helpers ───────────────────────────────────────────────

    def _check_budget(self, state: RunState) -> tuple[bool, str]:
        """Return (ok, reason_if_not_ok)."""
        m = state.metrics
        if m.llm_calls >= self._cfg.max_llm_calls:
            return False, f"LLM call budget exhausted ({m.llm_calls}/{self._cfg.max_llm_calls})"
        if m.estimated_tokens >= self._cfg.max_token_budget:
            return False, f"Token budget exhausted ({m.estimated_tokens}/{self._cfg.max_token_budget})"
        if not state.started_at:
            return True, ""
        from datetime import datetime, timezone
        try:
            dt = datetime.fromisoformat(state.started_at)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - dt).total_seconds()
        except Exception:
            return True, ""
        if elapsed >= self._cfg.max_runtime_seconds:
            return False, f"Runtime timeout ({int(elapsed)}s/{self._cfg.max_runtime_seconds}s)"
        return True, ""

    def _check_internet(self) -> bool:
        policy = self._cfg.internet_policy
        if policy == "off":
            return False
        return True

    # ── Bootstrap ────────────────────────────────────────────────────

    def _bootstrap(self, state: RunState) -> RunState:
        """Verify environment is ready."""
        cfg_mgr = self._config_manager
        if not cfg_mgr.ready:
            return state.transition(
                RunStatus.FAILED, RunPhase.BOOTSTRAP,
                error=f"ConfigManager not ready: {cfg_mgr.error}",
            )
        # Verify project exists
        if state.project_id and not self._pm.project_exists(state.project_id):
            return state.transition(
                RunStatus.FAILED, RunPhase.BOOTSTRAP,
                error=f"Project not found: {state.project_id}",
            )
        return state.transition(RunStatus.RUNNING, RunPhase.PLANNING)

    # ── Planning ─────────────────────────────────────────────────────

    def _plan(self, state: RunState) -> tuple[RunState, Optional[Plan]]:
        """Generate initial plan via LLM."""
        if not self._check_internet():
            # In offline mode, use Mock planner
            from core.planner.planner import MockPlannerProvider
            planner = Planner(provider=MockPlannerProvider())
        else:
            planner = self._get_planner()

        result: PlanResult = planner.plan(state.project_id, state.goal)
        state = self._record_llm_metrics(state, result)

        if result.error or not result.plan:
            return state.transition(
                RunStatus.FAILED, RunPhase.PLANNING,
                error=result.error or "Plan generation failed",
            ), None

        # Validate the plan
        validation = result.validation
        if not validation.valid:
            err_msg = "; ".join(
                f"[{e.code}] {e.message}" for e in validation.errors
            )
            return state.transition(
                RunStatus.FAILED, RunPhase.PLANNING,
                error=f"Plan validation failed: {err_msg}",
            ), None

        # Store plan JSON
        import json
        plan_json = result.plan.to_json()
        state.plan_json = plan_json
        state.plan_version = 1

        return state.transition(RunStatus.RUNNING, RunPhase.REFINING), result.plan

    # ── Plan refinement ──────────────────────────────────────────────

    def _refine_plan(self, state: RunState,
                     plan: Plan) -> tuple[RunState, Plan]:
        """Refine plan up to MAX_PLAN_REFINEMENTS times."""
        current_plan = plan
        for i in range(self._cfg.max_plan_refinements):
            issues = self._detect_plan_issues(current_plan)
            if not issues:
                break

            # Deterministic refinements (no LLM needed for simple fixes)
            refined = self._apply_refinements(current_plan, issues)
            if refined == current_plan:
                break

            current_plan = refined
            state.plan_version += 1
            import json
            state.plan_json = current_plan.to_json()

        return state, current_plan

    def _detect_plan_issues(self, plan: Plan) -> list[str]:
        """Detect fixable plan issues without LLM."""
        issues = []
        if not plan.steps:
            issues.append("EMPTY_PLAN")
            return issues

        # Check for empty steps
        for s in plan.steps:
            if not s.command and s.step_type == "shell":
                issues.append(f"MISSING_COMMAND:{s.step_id}")
            if not s.title:
                issues.append(f"MISSING_TITLE:{s.step_id}")
            if s.dependencies:
                # Check each dependency references an existing step
                step_ids = {s2.step_id for s2 in plan.steps}
                for d in s.dependencies:
                    if d not in step_ids:
                        issues.append(f"BAD_DEP:{s.step_id}:{d}")

        # Check for overly large steps (> 2000 chars command — likely needs split)
        for s in plan.steps:
            if s.step_type == "shell" and len(s.command) > 2000:
                issues.append(f"OVERLY_LARGE:{s.step_id}")

        return issues

    def _apply_refinements(self, plan: Plan,
                            issues: list[str]) -> Plan:
        """Apply deterministic refinements. Returns same plan if nothing to fix."""
        plan = copy.deepcopy(plan)

        for issue in issues:
            if issue == "EMPTY_PLAN":
                continue  # can't fix without LLM

            if issue.startswith("MISSING_COMMAND:"):
                step_id = issue.split(":", 1)[1]
                for s in plan.steps:
                    if s.step_id == step_id:
                        s.command = "# placeholder — needs attention"
                continue

            if issue.startswith("MISSING_TITLE:"):
                step_id = issue.split(":", 1)[1]
                for s in plan.steps:
                    if s.step_id == step_id:
                        s.title = s.title or f"Untitled step {s.step_id}"
                continue

        return plan

    # ── Execution ────────────────────────────────────────────────────

    def _execute_task(self, state: RunState,
                      plan: Plan) -> tuple[RunState, list[Task]]:
        """Execute all steps of the plan as individual tasks."""
        tasks: list[Task] = []
        step = state.current_task_index

        while step < len(plan.steps):
            s = plan.steps[step]
            state = state.transition(RunStatus.RUNNING, RunPhase.EXECUTING)
            state.recovery_point = f"Task {step + 1}/{len(plan.steps)}: {s.title}"

            # Budget check before each task
            ok, reason = self._check_budget(state)
            if not ok:
                return state.transition(
                    RunStatus.BUDGET_EXCEEDED, RunPhase.STOPPED,
                    error=reason,
                ), tasks

            # Create task for this step
            task = plan_to_task(plan)
            # Override task to contain just this step
            task.task_id = f"TASK-RUN-{state.run_id}-S{step:03d}"
            task.title = s.title
            task.description = s.description
            task.steps = [self._step_from_plan_step(s)]
            task = self._tm.create_task(
                project_id=state.project_id,
                title=task.title,
                description=task.description,
                steps=task.steps,
            )

            # Update state with new task
            state.current_task_index = step
            state = self._checkpoint(state)

            # Run the task
            task = self._tr.run(task)
            state = self._record_task_result(state, task, step)
            tasks.append(task)

            # Observe
            obs = self._observe_task(task)
            state.last_observation = obs[-500:] if len(obs) > 500 else obs

            # Verify
            verified = self._verify_task(state, task)

            if task.status == TaskStatus.FAILED or not verified:
                # Failure — try to diagnose and recover
                state, recovered = self._handle_failure(state, task, s)
                if not recovered:
                    return state, tasks
            elif verified:
                state.completed_task_ids.append(task.task_id)
                state.current_task_index += 1

            # Save checkpoint after each task
            state = self._checkpoint(state)
            step = state.current_task_index

        return state, tasks

    def _step_from_plan_step(self, ps: PlanStep) -> TaskStep:
        """Convert PlanStep → TaskStep."""
        step_type = {
            "shell": StepType.SHELL,
            "python": StepType.PYTHON,
            "inspect": StepType.INSPECT,
        }.get(ps.step_type, StepType.SHELL)

        return TaskStep(
            type=step_type,
            title=ps.title,
            description=ps.description,
            command=ps.command,
            args=ps.arguments,
            expect_exit_code=ps.expect_exit_code,
            verify_contains=ps.verify_contains,
            verify_not_contains=ps.verify_not_contains,
        )

    def _observe_task(self, task: Task) -> str:
        """Extract last non-empty stdout snippet."""
        for step in reversed(task.steps):
            if step.result and step.result.stdout:
                return step.result.stdout
        if task.error:
            return task.error
        return ""

    def _verify_task(self, state: RunState, task: Task) -> bool:
        """Verify task result. Uses existing TaskRunner verification."""
        return (
            task.status == TaskStatus.COMPLETED and
            task.verification and task.verification.verified
        )

    def _record_llm_metrics(self, state: RunState,
                            result: PlanResult) -> RunState:
        """Update metrics after an LLM call."""
        state = copy.deepcopy(state)
        state.metrics.llm_calls += 1
        if result.context_stats:
            state.metrics.estimated_tokens += result.context_stats.approx_tokens
        return state

    def _record_task_result(self, state: RunState, task: Task,
                             step_index: int) -> RunState:
        """Update state after a task completes or fails."""
        state = copy.deepcopy(state)
        if task.status == TaskStatus.FAILED:
            state.failed_task_ids.append(task.task_id)
        return state

    # ── Failure recovery ─────────────────────────────────────────────

    def _handle_failure(self, state: RunState, task: Task,
                        step: PlanStep) -> tuple[RunState, bool]:
        """Diagnose failure and attempt local recovery.

        Returns (updated_state, recovered_successfully).
        """
        error_msg = task.error or "Unknown error"
        step_result_dict = None
        if task.steps and task.steps[0].result:
            r = task.steps[0].result
            step_result_dict = {
                "stdout": r.stdout,
                "stderr": r.stderr,
                "exit_code": r.exit_code,
            }

        diagnosis, can_recover = _diagnose_failure(
            error_msg, task.steps[0] if task.steps else TaskStep(type=StepType.SHELL),
            step_result_dict,
        )

        state.retry_reason = diagnosis
        state.attempt_count += 1

        if not can_recover:
            # Non-recoverable — escalate to LLM or fail
            if state.metrics.llm_calls < self._cfg.max_llm_calls:
                state, fixed = self._llm_repair(state, task, step, diagnosis)
                if fixed:
                    return state, True
            return state.transition(
                RunStatus.BLOCKED, RunPhase.STOPPED,
                error=f"Non-recoverable: {diagnosis}",
            ), False

        # Local recovery — retry
        state.retry_count += 1
        if state.retry_count > self._cfg.max_retries:
            return state.transition(
                RunStatus.FAILED, RunPhase.STOPPED,
                error=f"Retry limit exceeded: {diagnosis}",
            ), False

        # Retry — advance to next task (mark as failed, continue)
        state = state.transition(RunStatus.RUNNING, RunPhase.RETRY)
        state.current_task_index += 1
        return self._checkpoint(state), True

    def _llm_repair(self, state: RunState, task: Task,
                     step: PlanStep, diagnosis: str) -> tuple[RunState, bool]:
        """Ask LLM to suggest a repair for a failed step."""
        state = state.transition(RunStatus.RUNNING, RunPhase.ESCALATING)

        if not self._check_internet():
            # No internet + internet not required → can't escalate
            return state, False

        # Build minimal repair prompt
        system = (
            "You are a coding assistant. Given a failed step and a diagnosis, "
            "return a JSON object with a 'fixed_command' string (shell command) "
            "or 'suggestion' string, and 'reasoning' string. No extra text."
        )
        user = (
            f"Goal: {state.goal}\n"
            f"Failed step: {step.title}\n"
            f"Command: {step.command}\n"
            f"Diagnosis: {diagnosis}\n"
            f"Error: {task.error}\n"
            "Return: {\"fixed_command\": \"...\"} or {\"suggestion\": \"...\", \"reasoning\": \"...\"}"
        )

        try:
            planner = self._get_planner()
            result = planner._provider.generate(system, user)  # noqa: SLF001
            state = self._record_llm_metrics(state, PlanResult(
                plan=None, validation=ValidationResult(valid=True),
                raw_llm_output=result, context_stats=None, provider_name="runtime",
            ))
            # Don't apply the fix automatically — mark as BLOCKED for user review
            return state.transition(
                RunStatus.BLOCKED, RunPhase.STOPPED,
                error=f"LLM repair suggestion available: {result[:200]}",
            ), False
        except Exception as e:
            return state.transition(
                RunStatus.BLOCKED, RunPhase.STOPPED,
                error=f"LLM repair failed: {e}",
            ), False

    # ── Checkpoint ───────────────────────────────────────────────────

    def _checkpoint(self, state: RunState) -> RunState:
        """Atomic checkpoint save."""
        saved = self._store.save(state)
        return state

    # ── Finalization ─────────────────────────────────────────────────

    def _finalize(self, state: RunState, tasks: list[Task]) -> RunState:
        """Run final verification and set terminal status."""
        state = state.transition(RunStatus.RUNNING, RunPhase.VERIFYING)

        if not tasks:
            return state.transition(
                RunStatus.FAILED, RunPhase.STOPPED,
                error="No tasks were executed",
            )

        all_verified = all(
            t.status == TaskStatus.COMPLETED and
            (t.verification and t.verification.verified)
            for t in tasks
        )

        if all_verified:
            return state.transition(
                RunStatus.COMPLETED, RunPhase.STOPPED,
                observation="All tasks verified",
            )
        elif any(t.status == TaskStatus.COMPLETED for t in tasks):
            # Some tasks passed
            passed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
            return state.transition(
                RunStatus.COMPLETED, RunPhase.STOPPED,
                error=f"{passed}/{len(tasks)} tasks completed (some unverified)",
            )
        else:
            return state.transition(
                RunStatus.FAILED, RunPhase.STOPPED,
                error=f"All {len(tasks)} tasks failed",
            )

    # ── Idempotent resume ────────────────────────────────────────────

    def _inspect_actual_state(self, state: RunState,
                               plan: Plan) -> RunState:
        """Inspect filesystem to determine what was actually done.

        This is called on resume to avoid re-running completed work.
        """
        step = state.current_task_index
        if step >= len(plan.steps):
            return state  # nothing left

        s = plan.steps[step]
        # Check if work was already done (deterministic checks)
        # For shell commands with file outputs, we can check file existence
        # This is a simplified heuristic
        return state  # by default, trust the checkpoint

    # ── Public API ───────────────────────────────────────────────────

    def run(self, project_id: str, goal: str,
            run_id: Optional[str] = None) -> RunState:
        """Execute a goal end-to-end with durable checkpoints."""
        def _make_now_str() -> str:
            from datetime import datetime, timezone
            return datetime.now(timezone.utc).isoformat()

        # Create or load state
        if run_id and self._store.exists(run_id):
            state = self._store.load(run_id)
            if state is None:
                raise ValueError(f"Corrupt checkpoint for run: {run_id}")
            # Resume — inspect actual state first
            if state.plan_json and state.status == RunStatus.RUNNING.value:
                plan = Plan.from_json(state.plan_json)
                state = self._inspect_actual_state(state, plan)
        else:
            # New run
            if run_id is None:
                import time as _time
                seq = int(_time.time() * 1000) % 100000
                run_id = f"RUN-{seq:05d}"
            state = RunState(
                run_id=run_id,
                goal=goal,
                project_id=project_id,
                status=RunStatus.PENDING.value,
                phase=RunPhase.BOOTSTRAP.value,
                started_at=_make_now_str(),
                max_llm_calls=self._cfg.max_llm_calls,
                max_token_budget=self._cfg.max_token_budget,
                max_plan_refinements=self._cfg.max_plan_refinements,
                max_retries=self._cfg.max_retries,
                max_runtime_seconds=self._cfg.max_runtime_seconds,
                internet_policy=self._cfg.internet_policy,
            )

        # Bootstrap
        state = self._bootstrap(state)
        self._checkpoint(state)
        if state.status != RunStatus.RUNNING.value:
            return state

        # Plan
        state, plan = self._plan(state)
        self._checkpoint(state)
        if plan is None:
            return state

        # Refine
        state, plan = self._refine_plan(state, plan)
        self._checkpoint(state)

        # Execute
        state, tasks = self._execute_task(state, plan)
        self._checkpoint(state)

        # Finalize
        state = self._finalize(state, tasks)
        self._checkpoint(state)

        return state

    # ── Resume ──────────────────────────────────────────────────────

    def resume(self, run_id: str) -> RunState:
        """Resume an interrupted run from its checkpoint."""
        state = self._store.load(run_id)
        if state is None:
            raise ValueError(f"Run not found: {run_id}")

        # Resume the run with the same run_id
        return self.run(state.project_id, state.goal, run_id=run_id)

    # ── Inspect ─────────────────────────────────────────────────────

    def get_state(self, run_id: str) -> Optional[RunState]:
        return self._store.load(run_id)

    def list_runs(self) -> list[str]:
        return self._store.list_runs()

    def stop(self, run_id: str, reason: str = "User requested") -> RunState:
        """Gracefully stop a run, writing final checkpoint."""
        state = self._store.load(run_id)
        if state is None:
            raise ValueError(f"Run not found: {run_id}")
        state = state.transition(
            RunStatus.INTERRUPTED, RunPhase.STOPPED,
            error=reason,
        )
        self._checkpoint(state)
        return state
