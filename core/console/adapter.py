# core/console/adapter.py
"""Adapter: RuntimeEngine + KernelOrchestrator → EventBus.

Wires RuntimeEngine events into the global EventBus so the
Live Console can observe real runs.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

from core.events.bus import get_bus
from core.events.schema import EventPhase, EventStatus, new_event

if TYPE_CHECKING:
    from core.runtime.engine import RuntimeEngine
    from core.runtime.schema import RunState, RunPhase
    from core.tasks.schema import Task, TaskStatus

logger = logging.getLogger(__name__)

# Persistent events file for cross-process visibility
_EVENTS_PATH = Path("/tmp/agent-core-events.json")


class RuntimeEventAdapter:
    """Subscribes to RuntimeEngine phase transitions and emits AgentEvents.

    This adapter is passive — it observes RuntimeEngine internals via
    callbacks rather than patching the engine itself.
    """

    def __init__(self, engine: "RuntimeEngine"):
        self._engine = engine
        self._bus = get_bus()
        self._run_id: str | None = None
        self._task_count = 0

    def on_run_start(self, run_id: str, goal: str, project_id: str) -> None:
        """Called when a run begins."""
        self._run_id = run_id
        self._task_count = 0
        self._emit(run_id, EventPhase.PLAN.value,
                   f"Run started: {goal[:60]}",
                   EventStatus.RUNNING.value,
                   metadata={"goal": goal[:100], "project_id": project_id})

    def on_phase(self, run_id: str, phase: str, status: str = "RUNNING",
                 message: str = "") -> None:
        self._emit(run_id, phase, message or phase, status)

    def on_checkpoint(self, run_id: str, index: int,
                      recovery_point: str = "") -> None:
        self._emit(run_id, EventPhase.CHECKPOINT.value,
                   f"Checkpoint #{index}: {recovery_point}",
                   EventStatus.OK.value,
                   metadata={"checkpoint_index": index})

    def on_task_start(self, run_id: str, task: "Task") -> None:
        self._task_count += 1
        self._emit(run_id, EventPhase.EXECUTE.value,
                   f"[{self._task_count}] {task.title or task.task_id}",
                   EventStatus.RUNNING.value,
                   task_id=task.task_id,
                   metadata={"step_count": len(task.steps)})

    def on_task_result(self, run_id: str, task: "Task",
                       duration: float = 0.0) -> None:
        status_map = {
            "COMPLETED": EventStatus.PASS.value,
            "FAILED": EventStatus.FAIL.value,
        }
        status_val = task.status.value if hasattr(task.status, "value") else str(task.status)
        ev_status = status_map.get(status_val, EventStatus.OK.value)
        self._emit(run_id, EventPhase.EXECUTE.value,
                   f"[{self._task_count}] {task.title}: {status_val}",
                   ev_status,
                   task_id=task.task_id,
                   duration=duration,
                   metadata=self._task_metadata(task))

    def on_observe(self, run_id: str, observation: str) -> None:
        # Truncate long observation
        obs_short = observation[:200] if observation else ""
        self._emit(run_id, EventPhase.OBSERVE.value,
                   obs_short,
                   EventStatus.OK.value,
                   metadata={"observation_len": len(observation)})

    def on_verify(self, run_id: str, verified: bool,
                  message: str = "") -> None:
        self._emit(run_id, EventPhase.VERIFY.value,
                   "Verification " + ("PASS" if verified else "FAIL"),
                   EventStatus.PASS.value if verified else EventStatus.FAIL.value,
                   metadata={"verified": verified, "message": message[:100]})

    def on_recovery(self, run_id: str, reason: str,
                    recovered: bool) -> None:
        self._emit(run_id, EventPhase.RECOVERY.value,
                   f"Recovery: {reason[:60]}",
                   EventStatus.OK.value if recovered else EventStatus.FAIL.value,
                   metadata={"recovered": recovered, "reason": reason[:200]})

    def on_run_end(self, run_id: str, state: "RunState") -> None:
        status = state.status
        if not isinstance(status, str):
            status = status.value
        phase = state.phase
        if not isinstance(phase, str):
            phase = phase.value
        verdict = EventStatus.OK.value if status == "COMPLETED" else EventStatus.FAIL.value
        self._emit(run_id, EventPhase.RESULT.value,
                   f"Run {status} — {phase}",
                   verdict,
                   metadata={
                       "run_status": status,
                       "llm_calls": state.metrics.llm_calls,
                       "estimated_tokens": state.metrics.estimated_tokens,
                       "completed_tasks": len(state.completed_task_ids),
                       "failed_tasks": len(state.failed_task_ids),
                       "retry_count": state.retry_count,
                   })

    # ── Internals ──────────────────────────────────────────────────

    def _emit(self, run_id: str, phase: str, action: str,
              status: str = EventStatus.RUNNING.value,
              **kwargs) -> None:
        ev = new_event(run_id=run_id, phase=phase, action=action,
                       status=status, **kwargs)
        try:
            self._bus.publish(ev)
            # Persist to disk for cross-process visibility
            _EVENTS_PATH.write_text(
                json.dumps([e.to_dict() for e in self._bus._buffer], default=str)
            )
        except Exception:
            logger.warning("EventBus publish failed (adapter): %s",
                           __import__("traceback").format_exc())

    def _task_metadata(self, task: "Task") -> dict:
        status_val = (
            task.status.value
            if hasattr(task.status, "value")
            else str(task.status)
        )
        meta = {"task_id": task.task_id, "status": status_val}
        if task.steps:
            s = task.steps[0]
            if s.result:
                meta["exit_code"] = s.result.exit_code
                if s.result.stderr:
                    meta["stderr_preview"] = s.result.stderr[:100]
        if task.verification:
            meta["verified"] = task.verification.verified
        return meta


# ── Patched RuntimeEngine ───────────────────────────────────────────

def patch_runtime_engine() -> None:
    """Monkey-patch RuntimeEngine to emit events.

    Safe: only adds instrumentation, never changes semantics.
    One adapter instance per engine instance.
    """
    from core.runtime import engine as rt_module

    if hasattr(rt_module, "_events_patched"):
        return

    RuntimeEngine = rt_module.RuntimeEngine

    _original_run = RuntimeEngine.run
    _original_resume = RuntimeEngine.resume

    def patched_run(self, project_id, goal, run_id=None):
        adapter = RuntimeEventAdapter(self)
        run_id_out = None

        # Intercept run_id by wrapping checkpoint save
        _orig_checkpoint = self._checkpoint

        def event_checkpoint(state):
            result = _orig_checkpoint(state)
            # Emit phase change events
            phase = state.phase
            if not isinstance(phase, str):
                phase = phase.value
            if phase == "BOOTSTRAP":
                adapter.on_run_start(state.run_id, goal, project_id)
            elif phase == "PLANNING":
                adapter.on_phase(state.run_id, EventPhase.PLAN.value, "RUNNING",
                                 "Generating plan")
            elif phase == "REFINING":
                adapter.on_phase(state.run_id, EventPhase.PLAN.value, "RUNNING",
                                 "Refining plan")
            elif phase == "EXECUTING":
                adapter.on_phase(state.run_id, EventPhase.EXECUTE.value,
                                 "RUNNING", "Executing tasks")
            elif phase == "VERIFYING":
                adapter.on_phase(state.run_id, EventPhase.VERIFY.value,
                                 "RUNNING", "Verifying results")
            elif phase == "STOPPED":
                adapter.on_run_end(state.run_id, state)
            return result

        self._checkpoint = event_checkpoint

        # Patch task execution to emit task events
        _orig_execute = self._execute_task

        def patched_execute(state, plan):
            nonlocal run_id_out
            run_id_out = state.run_id
            adapter.on_phase(state.run_id, EventPhase.EXECUTE.value,
                             "RUNNING", f"Executing {len(plan.steps)} step(s)")

            # Intercept task results
            _orig_record = self._record_task_result

            def event_record(state, task, step_index):
                result = _orig_record(state, task, step_index)
                adapter.on_task_result(state.run_id, task)
                return result

            self._record_task_result = event_record

            # Intercept observations
            _orig_observe = self._observe_task

            def event_observe(task):
                obs = _orig_observe(task)
                if run_id_out:
                    adapter.on_observe(run_id_out, obs)
                return obs

            self._observe_task = event_observe

            # Intercept verification
            _orig_verify = self._verify_task

            def event_verify(state, task):
                result = _orig_verify(state, task)
                if run_id_out:
                    adapter.on_verify(run_id_out, result)
                return result

            self._verify_task = event_verify

            return _orig_execute(state, plan)

        self._execute_task = patched_execute

        return _original_run(self, project_id, goal, run_id)

    def patched_resume(self, run_id):
        adapter = RuntimeEventAdapter(self)

        # Patch checkpoint to emit events
        _orig_checkpoint = self._checkpoint

        def event_checkpoint(state):
            result = _orig_checkpoint(state)
            phase = state.phase
            if not isinstance(phase, str):
                phase = phase.value
            if phase == "EXECUTING":
                adapter.on_phase(state.run_id, EventPhase.EXECUTE.value,
                                 "RUNNING", "Resuming execution")
            elif phase == "STOPPED":
                adapter.on_run_end(state.run_id, state)
            return result

        self._checkpoint = event_checkpoint
        return _original_resume(self, run_id)

    RuntimeEngine.run = patched_run
    RuntimeEngine.resume = patched_resume
    rt_module._events_patched = True
