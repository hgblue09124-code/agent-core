# core/runtime/observe.py
"""Observer — accept relevant events. Deterministic. No LLM."""

from __future__ import annotations

from core.runtime.models import AgentPhase, RuntimeEvent, RuntimeEventKind
from core.runtime.objective_store import ObjectiveStore


class Observer:
    """Classify whether an event should start a cycle.

    Returns: irrelevant | informational | associated | actionable | requiring_user.
    """

    def __init__(self, store: ObjectiveStore):
        self._store = store

    def classify(self, event: RuntimeEvent, *, previous_phase: str = "") -> str:
        if event.kind == RuntimeEventKind.APPROVAL.value:
            return "requiring_user"
        text = event.text().strip()
        if event.kind == RuntimeEventKind.USER_INPUT.value and not text:
            return "irrelevant"
        if event.kind in {
            RuntimeEventKind.EXTERNAL_RESULT.value,
            RuntimeEventKind.SCHEDULED.value,
            RuntimeEventKind.TASK_COMPLETED.value,
            RuntimeEventKind.INTEGRATION.value,
        }:
            if previous_phase in {AgentPhase.WATCHING.value, AgentPhase.WAITING.value}:
                return "associated"
            if self._store.match(text or str(event.payload)):
                return "associated"
            return "informational"
        if event.kind == RuntimeEventKind.USER_INPUT.value:
            return "actionable"
        return "informational"
