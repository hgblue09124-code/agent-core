# core/executor/__init__.py
"""Agent Executor v0.3 — connects Planner → Task Engine.

Pipeline:
    User Goal → Planner.plan() → Plan → plan_to_task()
    → TaskManager.create_task() → TaskRunner.run() → Result

LLM = PLANNER
TaskRunner = EXECUTOR
Verification = AUTHORITY
Executor = ORCHESTRATOR (stateless, delegates)
"""

from core.executor.executor import AgentExecutor, ExecutorResult

__all__ = ["AgentExecutor", "ExecutorResult"]
