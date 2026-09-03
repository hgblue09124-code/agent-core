# core/events/schema.py
"""Live Activity Console v1.1 — AgentEvent schema.

An AgentEvent is a structured observation emitted by the kernel at
each phase. It is the source of truth for the live activity stream.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class EventPhase(str, Enum):
    PLAN         = "PLAN"
    KNOWLEDGE    = "KNOWLEDGE"
    EXECUTE      = "EXECUTE"
    OBSERVE      = "OBSERVE"
    VERIFY       = "VERIFY"
    RECOVERY     = "RECOVERY"
    CHECKPOINT   = "CHECKPOINT"
    EXPERIENCE   = "EXPERIENCE"
    EVALUATION   = "EVALUATION"
    RESULT       = "RESULT"


class EventStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASS    = "PASS"
    FAIL    = "FAIL"
    OK      = "OK"
    ERROR   = "ERROR"


@dataclass
class AgentEvent:
    """A single kernel activity event."""
    event_id: str
    run_id: str
    phase: str           # EventPhase
    action: str
    status: str          # EventStatus
    timestamp: str = ""
    task_id: str = ""
    message: str = ""
    duration: float = 0.0
    metadata: dict = field(default_factory=dict)
    schema_version: int = 1

    # ── Serialisation ────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "run_id": self.run_id,
            "phase": self.phase,
            "action": self.action,
            "status": self.status,
            "timestamp": self.timestamp,
            "task_id": self.task_id,
            "message": self.message,
            "duration": self.duration,
            "metadata": dict(self.metadata),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AgentEvent":
        return cls(
            event_id=d["event_id"],
            run_id=d["run_id"],
            phase=d.get("phase", EventPhase.RESULT.value),
            action=d.get("action", ""),
            status=d.get("status", EventStatus.PENDING.value),
            timestamp=d.get("timestamp", ""),
            task_id=d.get("task_id", ""),
            message=d.get("message", ""),
            duration=float(d.get("duration", 0.0)),
            metadata=dict(d.get("metadata", {})),
            schema_version=int(d.get("schema_version", 1)),
        )

    # ── Helpers ──────────────────────────────────────────────────────

    def now_str(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def short_ts(self) -> str:
        """Return HH:MM:SS portion of timestamp, suitable for console."""
        if not self.timestamp:
            return ""
        # Take the time portion from an ISO string
        try:
            # Handle "2026-01-01T10:21:04" or "2026-01-01T10:21:04.123456+00:00"
            time_part = self.timestamp.split("T")[-1]
            return time_part.split("+")[0].split(".")[0]
        except Exception:
            return self.timestamp


def new_event(run_id: str, phase: str, action: str,
              status: str = EventStatus.RUNNING.value,
              **kwargs) -> AgentEvent:
    """Factory: create a new event with auto-id and timestamp."""
    return AgentEvent(
        event_id=f"EV-{uuid.uuid4().hex[:10]}",
        run_id=run_id,
        phase=phase,
        action=action,
        status=status,
        timestamp=datetime.now(timezone.utc).isoformat(),
        **kwargs,
    )
