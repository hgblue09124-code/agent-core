# core/tasks/__init__.py
"""Task Engine — deterministic task management for registered projects.

v0.1: project-aware kernel, no LLM, no eval(), stdlib only.
"""

from core.tasks.schema import (
    TaskStatus,
    StepType,
    TaskStep,
    VerificationResult,
    Task,
)
from core.tasks.manager import TaskManager
from core.tasks.context import TaskContext
from core.tasks.runner import TaskRunner

__all__ = [
    "TaskStatus",
    "StepType",
    "TaskStep",
    "VerificationResult",
    "Task",
    "TaskManager",
    "TaskContext",
    "TaskRunner",
]
