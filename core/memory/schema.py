# core/memory/schema.py
"""Memory schema — items, types, and queries for Agent-Core memory subsystem."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class MemoryType(str, Enum):
    SHORT_TERM = "SHORT_TERM"     # Active context / recent task observations
    LONG_TERM = "LONG_TERM"       # Durable knowledge / facts learned
    USER_CONTEXT = "USER_CONTEXT" # User preferences, relationship history, profile
    IDENTITY = "IDENTITY"         # Core agent persona, boundaries, self-description


@dataclass
class MemoryItem:
    """A single memory entry."""

    memory_id: str
    content: str
    memory_type: str = MemoryType.SHORT_TERM.value
    tags: list[str] = field(default_factory=list)
    importance: float = 0.5  # 0.0 (low) to 1.0 (critical)
    source_run_id: str = ""
    source_task_id: str = ""
    created_at: str = ""
    updated_at: str = ""
    metadata: dict = field(default_factory=dict)
    schema_version: int = 1

    def to_dict(self) -> dict:
        return {
            "memory_id": self.memory_id,
            "content": self.content,
            "memory_type": self.memory_type,
            "tags": list(self.tags),
            "importance": self.importance,
            "source_run_id": self.source_run_id,
            "source_task_id": self.source_task_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> MemoryItem:
        return cls(
            memory_id=d["memory_id"],
            content=d.get("content", ""),
            memory_type=d.get("memory_type", MemoryType.SHORT_TERM.value),
            tags=list(d.get("tags", [])),
            importance=float(d.get("importance", 0.5)),
            source_run_id=d.get("source_run_id", ""),
            source_task_id=d.get("source_task_id", ""),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            metadata=dict(d.get("metadata", {})),
            schema_version=int(d.get("schema_version", 1)),
        )

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()


@dataclass
class MemoryQuery:
    """Search query for memory retrieval."""

    query: str = ""
    memory_type: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    min_importance: float = 0.0
    limit: int = 5
