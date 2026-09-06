# core/runtime/action_executor.py
"""ActionExecutor — execute approved actions through controlled interfaces."""

from __future__ import annotations

from typing import Any, Optional

from core.capabilities.adapter import CapabilityRegistry
from core.capabilities.schema import CapabilityResult
from core.memory.manager import MemoryManager
from core.memory.schema import MemoryQuery, MemoryType
from core.runtime.models import Action, ActionType, ExecutionResult


class ActionExecutor:
    """Runs an Action. Does not authorize, verify, or mutate AgentState."""

    def __init__(self, capabilities: CapabilityRegistry, memory: MemoryManager):
        self._capabilities = capabilities
        self._memory = memory

    def execute(self, action: Action) -> ExecutionResult:
        action.execution_state = "EXECUTED"
        kind = action.type
        try:
            if kind == ActionType.REMEMBER.value:
                return self._remember(action)
            if kind == ActionType.FORGET.value:
                return self._forget(action)
            if kind == ActionType.RETRIEVE_MEMORY.value:
                return self._retrieve(action)
            if kind == ActionType.INVOKE_CAPABILITY.value:
                return self._invoke(action)
            if kind == ActionType.ECHO.value:
                text = str((action.arguments or {}).get("text") or "")
                return ExecutionResult(
                    success=True,
                    status="SUCCESS",
                    output={"echo": text or "ok"},
                    evidence={"echoed": True},
                    action_id=action.identifier,
                )
            if kind in {
                ActionType.ASK_USER.value,
                ActionType.WAIT.value,
                ActionType.WATCH.value,
                ActionType.FINISH.value,
                ActionType.NONE.value,
            }:
                action.execution_state = "SKIPPED"
                return ExecutionResult(
                    success=True,
                    status="SKIPPED",
                    output={"deferred": kind},
                    evidence={"side_effect": False},
                    action_id=action.identifier,
                )
            return ExecutionResult(
                success=False,
                status="FAILED",
                error=f"Unknown action type '{kind}'",
                action_id=action.identifier,
            )
        except Exception as exc:
            action.execution_state = "FAILED"
            return ExecutionResult(
                success=False,
                status="FAILED",
                error=str(exc),
                action_id=action.identifier,
            )

    def _remember(self, action: Action) -> ExecutionResult:
        args = action.arguments or {}
        content = str(args.get("content") or f"{args.get('key', '')}: {args.get('value', '')}").strip()
        if not content or content == ":":
            return ExecutionResult(
                success=False,
                status="FAILED",
                error="Remember action missing content",
                action_id=action.identifier,
            )
        item = self._memory.remember(
            content=content,
            memory_type=MemoryType.USER_CONTEXT.value,
            tags=["preference", str(args.get("key") or "")],
            importance=0.8,
            metadata={"key": args.get("key", ""), "value": args.get("value", "")},
        )
        output = {
            "remembered": item.memory_id,
            "key": args.get("key"),
            "value": args.get("value"),
            "content": content,
        }
        action.result = output
        return ExecutionResult(
            success=True,
            status="SUCCESS",
            output=output,
            evidence={"memory_id": item.memory_id},
            action_id=action.identifier,
        )

    def _forget(self, action: Action) -> ExecutionResult:
        args = action.arguments or {}
        ok = self._memory.forget(
            memory_id=str(args.get("memory_id") or ""),
            query=str(args.get("query") or args.get("key") or ""),
        )
        if not ok:
            return ExecutionResult(
                success=False,
                status="FAILED",
                error=f"Memory '{args.get('query') or args.get('key')}' not found",
                action_id=action.identifier,
            )
        output = {"forgotten": args.get("query") or args.get("key")}
        action.result = output
        return ExecutionResult(
            success=True,
            status="SUCCESS",
            output=output,
            evidence={"forgotten": True},
            action_id=action.identifier,
        )

    def _retrieve(self, action: Action) -> ExecutionResult:
        args = action.arguments or {}
        hits = self._memory.retrieve(MemoryQuery(query=str(args.get("query") or ""), limit=5))
        output = {"items": [h.content for h in hits]}
        return ExecutionResult(
            success=True,
            status="SUCCESS",
            output=output,
            evidence={"count": len(hits)},
            action_id=action.identifier,
        )

    def _invoke(self, action: Action) -> ExecutionResult:
        cap_id = action.capability
        if not cap_id:
            return ExecutionResult(
                success=False,
                status="FAILED",
                error="invoke_capability missing capability",
                action_id=action.identifier,
            )
        inputs: dict[str, Any] = dict(action.arguments or {})
        if action.operation and "action" not in inputs:
            inputs["action"] = action.operation
        result: CapabilityResult = self._capabilities.invoke(cap_id, inputs)
        action.result = result.output
        evidence = dict(result.metadata or {})
        evidence.setdefault("capability", cap_id)
        if action.operation:
            evidence.setdefault("operation", action.operation)
        return ExecutionResult(
            success=result.success,
            status=result.status,
            output=result.output,
            error=result.error or "",
            evidence=evidence,
            action_id=action.identifier,
        )
