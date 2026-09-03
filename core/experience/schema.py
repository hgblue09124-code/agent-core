# core/experience/schema.py
"""Experience Engine v0.8 — schemas & lifecycle.

An Experience record captures a single run of the agent attempting to achieve a goal.
It is immutable after creation (append-only) and serves as the source for lessons.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ── Experience Record ──────────────────────────────────────────────────

@dataclass
class Experience:
    """A single experience record.

    This is the atomic unit of learning. It is append-only: once recorded,
    it should not be mutated (except for correction via a new record).
    """
    # Identity
    run_id: str
    goal: str
    project_id: str

    # Context
    context_summary: str = ""

    # Execution
    task_id: str = ""
    action: str = ""          # what was attempted
    observation: str = ""     # what actually happened (raw)
    outcome: str = ""         # success/failure description
    failure: str = ""         # if any, what failed
    recovery: str = ""        # how we recovered (if we did)
    verification: str = ""    # how we verified the outcome

    # Cost
    cost: float = 0.0         # abstract cost unit
    duration: float = 0.0     # seconds
    llm_calls: int = 0
    estimated_tokens: int = 0

    # Learning
    lesson: str = ""          # extracted lesson (may be empty initially)

    # Metadata
    created_at: str = ""
    schema_version: int = 1

    # ── Serialisation ────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "goal": self.goal,
            "project_id": self.project_id,
            "context_summary": self.context_summary,
            "task_id": self.task_id,
            "action": self.action,
            "observation": self.observation,
            "outcome": self.outcome,
            "failure": self.failure,
            "recovery": self.recovery,
            "verification": self.verification,
            "cost": self.cost,
            "duration": self.duration,
            "llm_calls": self.llm_calls,
            "estimated_tokens": self.estimated_tokens,
            "lesson": self.lesson,
            "created_at": self.created_at,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Experience":
        return cls(
            run_id=d["run_id"],
            goal=d.get("goal", ""),
            project_id=d.get("project_id", ""),
            context_summary=d.get("context_summary", ""),
            task_id=d.get("task_id", ""),
            action=d.get("action", ""),
            observation=d.get("observation", ""),
            outcome=d.get("outcome", ""),
            failure=d.get("failure", ""),
            recovery=d.get("recovery", ""),
            verification=d.get("verification", ""),
            cost=float(d.get("cost", 0.0)),
            duration=float(d.get("duration", 0.0)),
            llm_calls=int(d.get("llm_calls", 0)),
            estimated_tokens=int(d.get("estimated_tokens", 0)),
            lesson=d.get("lesson", ""),
            created_at=d.get("created_at", ""),
            schema_version=int(d.get("schema_version", 1)),
        )

    # ── Helpers ──────────────────────────────────────────────────────

    def success(self) -> bool:
        """Heuristic: outcome indicates success."""
        return "success" in self.outcome.lower() or "pass" in self.outcome.lower()

    def now_str(self) -> str:
        return datetime.now(timezone.utc).isoformat()


# ── ID generation ───────────────────────────────────────────────────────

def generate_experience_id() -> str:
    """Generate a run_id-like identifier for experience (if needed)."""
    return f"EXP-{int(time.time() * 1000) % 100000:05d}"