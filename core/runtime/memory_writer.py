# core/runtime/memory_writer.py
"""MemoryWriter — persist only information with future value."""

from __future__ import annotations

from typing import Optional

from core.context.pack import clip, compact_tool_output
from core.memory.manager import MemoryManager
from core.memory.schema import MemoryType
from core.runtime.models import Action, ActionType, ExecutionResult, Objective, ObjectiveKind
from core.runtime.state import VerificationResult


class MemoryWriter:
    """Durable memory is not a transcript dump."""

    def __init__(self, memory: MemoryManager):
        self._memory = memory

    def maybe_write(
        self,
        *,
        action: Action,
        execution: ExecutionResult,
        verification: VerificationResult,
        objective: Objective,
    ) -> Optional[str]:
        if verification.verdict != "PASS":
            return None
        if action.type in {
            ActionType.REMEMBER.value,
            ActionType.FORGET.value,
            ActionType.RETRIEVE_MEMORY.value,
            ActionType.ECHO.value,
            ActionType.ASK_USER.value,
            ActionType.WAIT.value,
            ActionType.WATCH.value,
            ActionType.NONE.value,
        }:
            # Remember/forget already persisted by ActionExecutor.
            # Echo/control actions are not durable facts.
            return None
        if objective.kind == ObjectiveKind.PERSISTENT.value:
            return None
        if action.type != ActionType.INVOKE_CAPABILITY.value:
            return None
        if objective.status not in ("COMPLETED", "RUNNING"):
            return None

        summary = compact_tool_output(execution.output, max_chars=240)
        content = clip(
            f"Completed objective '{objective.intent}': {summary}",
            400,
        )
        item = self._memory.remember(
            content=content,
            memory_type=MemoryType.LONG_TERM.value,
            tags=["objective_result", objective.objective_id],
            importance=0.7,
            source_run_id=objective.objective_id,
            metadata={"objective_id": objective.objective_id, "kind": "objective_result"},
        )
        return item.memory_id
