# core/runtime/decide.py
"""v0.3 DecisionEngine — deterministic first, LLM only when necessary.

Provider-agnostic: depends on ReasoningProvider.reason(), never on a vendor.
"""

from __future__ import annotations

import json
import re
from typing import Optional, Protocol

from core.capabilities.adapter import CapabilityRegistry
from core.runtime.models import (
    Action,
    ActionType,
    Decision,
    DecisionContext,
    ReasoningLevel,
    RuntimeBounds,
    new_id,
)


class ReasoningProvider(Protocol):
    """Replaceable reasoning backend. Runtime must not branch on vendor."""

    def reason(self, system: str, user: str, *, level: str = "normal") -> str: ...


_WRITE_OPS = ("create", "update", "delete", "post", "put", "patch", "write", "comment", "merge")

_DECISION_SYSTEM = (
    "Return a single JSON object only. No chain-of-thought. "
    "Keys: intent, action_type, capability, operation, arguments, confidence, risk, verification, reason. "
    "action_type must be one of: echo, invoke_capability, remember, forget, ask_user, wait, watch, finish, none."
)


def parse_decision_json(text: str) -> Optional[dict]:
    """Deterministic parse. Natural language is not a Decision."""
    if not text or not str(text).strip():
        return None
    raw = str(text).strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    candidates = [raw]
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict) and data.get("action_type"):
            return data
    return None


class MockReasoningProvider:
    """Test double. Not a vendor backend."""

    def __init__(self, responses: Optional[list[str]] = None, default: Optional[str] = None):
        self.calls: list[dict] = []
        self._responses = list(responses or [])
        self.default = default or json.dumps(
            {
                "intent": "respond",
                "action_type": "echo",
                "arguments": {"text": "ok"},
                "confidence": 0.5,
                "risk": "LOW",
                "verification": "output",
                "reason": "mock",
            }
        )

    def reason(self, system: str, user: str, *, level: str = "normal") -> str:
        self.calls.append({"system": system, "user": user, "level": level})
        if self._responses:
            return self._responses.pop(0)
        return self.default


class DecisionEngine:
    """Produce a structured Decision. Never mutates Runtime state."""

    def __init__(
        self,
        registry: CapabilityRegistry,
        provider: Optional[ReasoningProvider] = None,
        bounds: Optional[RuntimeBounds] = None,
    ):
        self._registry = registry
        self._provider = provider
        self._bounds = bounds or RuntimeBounds()

    def decide(self, context: DecisionContext, *, llm_calls_used: int = 0) -> Decision:
        intent_kind = context.intent_kind
        intent_args = dict(context.intent_arguments or {})
        objective = context.objective or {}
        goal = str(objective.get("intent") or "")
        excluded = set(context.excluded_actions or [])

        if objective.get("kind") == "PERSISTENT" and not context.last_error:
            if context.event_kind in ("EXTERNAL_RESULT", "SCHEDULED", "TASK_COMPLETED", "INTEGRATION"):
                return self._deterministic(
                    intent=goal,
                    action_type=ActionType.WATCH.value,
                    arguments={"objective_id": objective.get("objective_id", "")},
                    reason="persistent objective has no new actionable work",
                )

        if intent_kind == "remember":
            return self._deterministic(
                intent=goal,
                action_type=ActionType.REMEMBER.value,
                arguments=intent_args,
                reason="deterministic remember",
            )
        if intent_kind == "forget":
            return self._deterministic(
                intent=goal,
                action_type=ActionType.FORGET.value,
                arguments=intent_args,
                reason="deterministic forget",
            )
        if intent_kind == "status":
            return self._deterministic(
                intent=goal,
                action_type=ActionType.ECHO.value,
                arguments={"text": goal},
                reason="deterministic status",
            )

        matched = self._match_capability(goal, excluded)
        if matched:
            cap_id, operation, risk = matched
            return self._deterministic(
                intent=goal,
                action_type=ActionType.INVOKE_CAPABILITY.value,
                arguments={"goal": goal, "action": operation},
                reason=f"deterministic capability route '{cap_id}.{operation}'",
                capability=cap_id,
                operation=operation,
                risk=risk,
            )

        needs_llm = not context.intent_cheap
        if not needs_llm or self._provider is None:
            return self._deterministic(
                intent=goal,
                action_type=ActionType.ECHO.value,
                arguments={"text": goal},
                reason="deterministic fallback; no LLM required or available",
            )

        if llm_calls_used >= self._bounds.max_llm_calls:
            return self._deterministic(
                intent=goal,
                action_type=ActionType.FINISH.value,
                arguments={},
                reason="LLM budget exhausted; refuse to escalate",
            )

        level = self._escalate(context, llm_calls_used)
        rendered = self._render(context, level)
        try:
            raw = self._provider.reason(_DECISION_SYSTEM, rendered, level=level.value.lower())
        except Exception as exc:
            return self._deterministic(
                intent=goal,
                action_type=ActionType.ECHO.value,
                arguments={"text": goal, "provider_error": str(exc)[:160]},
                reason=f"provider unavailable: {exc}",
                risk="LOW",
            )

        parsed = parse_decision_json(raw)
        if not parsed:
            return self._deterministic(
                intent=goal,
                action_type=ActionType.ECHO.value,
                arguments={"text": goal},
                reason="LLM output was not a structured Decision; ignored",
                llm_called=True,
            )
        return self._from_parsed(goal, parsed, level)

    def _escalate(self, context: DecisionContext, llm_calls_used: int) -> ReasoningLevel:
        if context.last_error and llm_calls_used >= 1:
            return ReasoningLevel.DEEP
        if context.excluded_actions:
            return ReasoningLevel.NORMAL
        return ReasoningLevel.CHEAP

    def _render(self, context: DecisionContext, level: ReasoningLevel) -> str:
        payload = context.to_dict()
        if level == ReasoningLevel.CHEAP:
            payload = {
                "event_kind": context.event_kind,
                "objective": {
                    "intent": context.objective.get("intent", ""),
                    "kind": context.objective.get("kind", ""),
                },
                "intent_kind": context.intent_kind,
            }
        elif level == ReasoningLevel.NORMAL:
            payload.pop("memory", None)
        return json.dumps(payload, ensure_ascii=False)

    def _match_capability(self, goal: str, excluded: set[str]) -> Optional[tuple[str, str, str]]:
        goal_lower = (goal or "").lower()
        if not goal_lower:
            return None
        for spec in self._registry.list_specs():
            cap_id = spec.capability_id
            if cap_id in excluded:
                continue
            name = (spec.name or "").lower()
            if cap_id.lower() not in goal_lower and not (name and name in goal_lower):
                continue
            if cap_id == "mock.echo":
                continue
            operation = "execute"
            gl = goal_lower
            if "create" in gl:
                operation = "create"
            elif "delete" in gl or "drop" in gl:
                operation = "delete"
            elif "update" in gl or "modify" in gl:
                operation = "update"
            elif "list" in gl:
                operation = "list"
            elif "inspect" in gl or "get" in gl:
                operation = "inspect"
            write = operation.startswith(_WRITE_OPS) or not spec.constraints.read_only
            risk = "HIGH" if write else "LOW"
            return cap_id, operation, risk
        return None

    def _from_parsed(self, goal: str, data: dict, level: ReasoningLevel) -> Decision:
        action_type = str(data.get("action_type") or ActionType.ECHO.value)
        allowed = {t.value for t in ActionType}
        if action_type not in allowed:
            action_type = ActionType.ECHO.value
        arguments = data.get("arguments") if isinstance(data.get("arguments"), dict) else {}
        capability = str(data.get("capability") or "")
        operation = str(data.get("operation") or "")
        if action_type == ActionType.INVOKE_CAPABILITY.value and not capability:
            action_type = ActionType.ECHO.value
        try:
            confidence = float(data.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))
        risk = str(data.get("risk") or "LOW").upper()
        if risk not in ("LOW", "MEDIUM", "HIGH"):
            risk = "LOW"
        action = Action(
            identifier=new_id("ACT"),
            type=action_type,
            arguments=dict(arguments),
            capability=capability,
            operation=operation,
            risk=risk,
            expected_outcome=str(data.get("verification") or ""),
        )
        return Decision(
            intent=str(data.get("intent") or goal),
            action=action,
            confidence=confidence,
            risk=risk,
            verification=str(data.get("verification") or ""),
            reasoning_level=level.value,
            llm_called=True,
            reason=str(data.get("reason") or "structured LLM decision"),
        )

    def _deterministic(
        self,
        *,
        intent: str,
        action_type: str,
        arguments: dict,
        reason: str,
        capability: str = "",
        operation: str = "",
        risk: str = "LOW",
        llm_called: bool = False,
    ) -> Decision:
        if action_type == ActionType.INVOKE_CAPABILITY.value:
            expected = intent
        elif action_type == ActionType.REMEMBER.value:
            expected = str(arguments.get("value") or arguments.get("content") or intent)
        elif action_type == ActionType.ECHO.value:
            expected = str(arguments.get("text") or intent)
        else:
            expected = ""
        action = Action(
            identifier=new_id("ACT"),
            type=action_type,
            arguments=dict(arguments),
            capability=capability,
            operation=operation,
            risk=risk,
            expected_outcome=expected,
        )
        return Decision(
            intent=intent,
            action=action,
            confidence=1.0,
            risk=risk,
            verification=expected,
            reasoning_level=ReasoningLevel.DETERMINISTIC.value if not llm_called else ReasoningLevel.CHEAP.value,
            llm_called=llm_called,
            reason=reason,
        )
