# core/memory/manager.py
"""Memory Manager — memory lifecycle, retrieval, and identity manager for Agent-Core."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from core.memory.schema import MemoryItem, MemoryType, MemoryQuery
from core.memory.store import MemoryStore


DEFAULT_IDENTITY_CONTENT = (
    "I am Agent-Core, a personal AI agent foundation built from small, verified "
    "primitives. I operate strictly under constitutional policy, verifying every "
    "action independently and maintaining experience continuity."
)


class MemoryManager:
    """Manages short-term, long-term, user context, and agent identity memory."""

    def __init__(self, store_dir: Optional[str] = None):
        self.store = MemoryStore(store_dir)
        self._ensure_default_identity()

    def _ensure_default_identity(self) -> None:
        """Ensure default identity memory exists on initialization."""
        identity_items = self.store.list_all(memory_type=MemoryType.IDENTITY.value)
        if not identity_items:
            now = datetime.now(timezone.utc).isoformat()
            item = MemoryItem(
                memory_id="IDENTITY-CORE",
                content=DEFAULT_IDENTITY_CONTENT,
                memory_type=MemoryType.IDENTITY.value,
                tags=["identity", "core", "persona"],
                importance=1.0,
                created_at=now,
                updated_at=now,
            )
            self.store.create(item)

    def remember(
        self,
        content: str,
        memory_type: str = MemoryType.SHORT_TERM.value,
        tags: Optional[list[str]] = None,
        importance: float = 0.5,
        source_run_id: str = "",
        source_task_id: str = "",
        metadata: Optional[dict] = None,
    ) -> MemoryItem:
        """Create and store a new memory item."""
        now = datetime.now(timezone.utc).isoformat()
        item = MemoryItem(
            memory_id=f"MEM-{uuid.uuid4().hex[:10]}",
            content=content,
            memory_type=memory_type,
            tags=tags or [],
            importance=importance,
            source_run_id=source_run_id,
            source_task_id=source_task_id,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        return self.store.create(item)

    def retrieve(self, query: MemoryQuery) -> list[MemoryItem]:
        """Retrieve relevant memory items matching type, tags, importance, or keywords."""
        all_items = self.store.list_all(memory_type=query.memory_type)
        results = []

        q_lower = query.query.lower().strip() if query.query else ""
        q_tokens = set(q_lower.split()) if q_lower else set()

        for item in all_items:
            if item.importance < query.min_importance:
                continue

            if query.tags:
                if not any(tag in item.tags for tag in query.tags):
                    continue

            # Keyword matching score
            if q_tokens:
                content_lower = item.content.lower()
                matches = sum(1 for tok in q_tokens if tok in content_lower)
                if matches == 0:
                    continue

            results.append(item)

        # Sort by importance * recency
        results.sort(key=lambda x: (x.importance, x.updated_at or x.created_at or ""), reverse=True)
        return results[: query.limit]

    def update(self, memory_id: str, new_content: str, importance: Optional[float] = None) -> Optional[MemoryItem]:
        """Update an existing memory item."""
        item = self.store.get(memory_id)
        if not item:
            return None

        item.content = new_content
        if importance is not None:
            item.importance = importance
        return self.store.update(item)

    def get_identity(self) -> MemoryItem:
        """Get the primary agent identity memory."""
        identity_items = self.store.list_all(memory_type=MemoryType.IDENTITY.value)
        if identity_items:
            return identity_items[0]
        # Fallback creation
        self._ensure_default_identity()
        return self.store.list_all(memory_type=MemoryType.IDENTITY.value)[0]

    def get_user_context(self) -> list[MemoryItem]:
        """Get user context memories."""
        return self.store.list_all(memory_type=MemoryType.USER_CONTEXT.value)
