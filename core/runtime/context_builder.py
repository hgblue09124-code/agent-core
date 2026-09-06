# core/runtime/context_builder.py
"""ContextBuilder — assemble only what the current decision requires."""

from __future__ import annotations

from typing import Any, Optional

from core.context.pack import clip, needed_layers
from core.memory.manager import MemoryManager
from core.memory.schema import MemoryQuery, MemoryType
from core.runtime.classify import GoalIntent
from core.runtime.models import (
    AgentState,
    DecisionContext,
    Objective,
    RuntimeBounds,
    RuntimeEvent,
)


class ContextBuilder:
    """Targeted retrieval. Never dumps conversation, full memory, or unrelated objectives."""

    def __init__(self, memory: MemoryManager, bounds: Optional[RuntimeBounds] = None):
        self._memory = memory
        self._bounds = bounds or RuntimeBounds()

    def build(
        self,
        event: RuntimeEvent,
        objective: Objective,
        state: AgentState,
        intent: GoalIntent,
        *,
        excluded_actions: Optional[list[str]] = None,
        last_error: str = "",
    ) -> DecisionContext:
        text = event.text() or objective.intent
        layers = set(needed_layers(text))
        if intent.kind in ("remember", "forget", "status"):
            layers = {"current_task"}
            if intent.kind == "forget":
                layers.add("retrieved")
        if intent.kind == "remember" and any(
            h in text.lower() for h in ("preference", "favorite", "theme")
        ):
            layers.add("retrieved")

        memories: list[dict[str, Any]] = []
        if "retrieved" in layers or "persistent" in layers:
            hits = self._memory.retrieve(
                MemoryQuery(query=text, limit=self._bounds.max_context_memories)
            )
            for item in hits:
                if item.memory_type == MemoryType.IDENTITY.value and "persistent" not in layers:
                    continue
                memories.append(
                    {
                        "memory_id": item.memory_id,
                        "content": clip(item.content, 200),
                        "memory_type": item.memory_type,
                    }
                )

        payload = dict(event.payload or {})
        payload_text = str(payload.get("text") or "")
        if len(payload_text) > 400:
            payload = dict(payload)
            payload["text"] = clip(payload_text, 400)

        ctx = DecisionContext(
            event_kind=event.kind,
            event_payload=payload,
            objective={
                "objective_id": objective.objective_id,
                "intent": clip(objective.intent, 300),
                "desired_outcome": clip(objective.desired_outcome, 200),
                "status": objective.status,
                "kind": objective.kind,
                "success_criteria": list(objective.success_criteria)[:4],
                "retry_count": objective.retry_count,
                "replan_count": objective.replan_count,
            },
            memory=memories,
            state={
                "phase": state.phase,
                "loop_iteration": state.loop_iteration,
                "llm_calls": state.llm_calls,
            },
            intent_kind=intent.kind,
            intent_cheap=intent.cheap,
            intent_arguments=dict(intent.arguments or {}),
            excluded_actions=list(excluded_actions or []),
            last_error=clip(last_error, 240),
            layers=sorted(layers),
        )
        self._enforce_budget(ctx)
        return ctx

    def _enforce_budget(self, ctx: DecisionContext) -> None:
        raw = str(ctx.to_dict())
        overflow = len(raw) - self._bounds.max_context_chars
        if overflow <= 0:
            return
        # Drop retrieved memory first; never drop current objective/event kind.
        while ctx.memory and len(str(ctx.to_dict())) > self._bounds.max_context_chars:
            ctx.memory.pop()
