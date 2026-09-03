# core/kernel/schema.py
"""Kernel schema — kernel-level state for the integrated loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class KernelPhase(str, Enum):
    BOOTSTRAP = "BOOTSTRAP"
    KNOWLEDGE_RETRIEVAL = "KNOWLEDGE_RETRIEVAL"
    REASONING = "REASONING"
    PLAN_VALIDATION = "PLAN_VALIDATION"
    EXECUTION = "EXECUTION"
    OBSERVATION = "OBSERVATION"
    VERIFICATION = "VERIFICATION"
    EXPERIENCE = "EXPERIENCE"
    EVALUATION = "EVALUATION"
    LESSON = "LESSON"
    KNOWLEDGE_PROMOTION = "KNOWLEDGE_PROMOTION"
    IMPROVEMENT = "IMPROVEMENT"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class KernelStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    RESUMED = "RESUMED"


@dataclass
class KernelContext:
    """Context for a kernel run."""
    run_id: str
    goal: str
    project_id: str
    kernel_phase: str = KernelPhase.BOOTSTRAP.value
    kernel_status: str = KernelStatus.PENDING.value
    knowledge_retrieved: list[str] = field(default_factory=list)
    plan: str = ""
    llm_calls: int = 0
    estimated_tokens: int = 0
    internet_enabled: bool = False
    errors: list[str] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "goal": self.goal,
            "project_id": self.project_id,
            "kernel_phase": self.kernel_phase,
            "kernel_status": self.kernel_status,
            "knowledge_retrieved": list(self.knowledge_retrieved),
            "plan": self.plan,
            "llm_calls": self.llm_calls,
            "estimated_tokens": self.estimated_tokens,
            "internet_enabled": self.internet_enabled,
            "errors": list(self.errors),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "KernelContext":
        return cls(
            run_id=d["run_id"],
            goal=d.get("goal", ""),
            project_id=d.get("project_id", ""),
            kernel_phase=d.get("kernel_phase", KernelPhase.BOOTSTRAP.value),
            kernel_status=d.get("kernel_status", KernelStatus.PENDING.value),
            knowledge_retrieved=list(d.get("knowledge_retrieved", [])),
            plan=d.get("plan", ""),
            llm_calls=int(d.get("llm_calls", 0)),
            estimated_tokens=int(d.get("estimated_tokens", 0)),
            internet_enabled=bool(d.get("internet_enabled", False)),
            errors=list(d.get("errors", [])),
            started_at=d.get("started_at", ""),
            finished_at=d.get("finished_at", ""),
            created_at=d.get("created_at", ""),
        )

    def now_str(self) -> str:
        return datetime.now(timezone.utc).isoformat()
