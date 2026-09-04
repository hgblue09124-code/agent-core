# core/memory/consolidation.py
"""Memory Consolidation & Conflict Resolution — consolidates short-term memories into long-term strategies and resolves conflicts."""

from __future__ import annotations

from typing import Optional

from core.memory.schema import MemoryItem, MemoryType, MemoryQuery
from core.memory.manager import MemoryManager
from core.learning.strategy import Strategy, StrategyStatus
from core.learning.store import StrategyStore
from core.learning.evaluator import StrategyEvaluator


class MemoryConsolidator:
    """Consolidates short-term memory observations into long-term knowledge and resolves knowledge/strategy conflicts."""

    def __init__(
        self,
        memory_manager: Optional[MemoryManager] = None,
        strategy_store: Optional[StrategyStore] = None,
        evaluator: Optional[StrategyEvaluator] = None,
    ):
        self.memory_manager = memory_manager or MemoryManager()
        self.strategy_store = strategy_store or StrategyStore()
        self.evaluator = evaluator or StrategyEvaluator(store=self.strategy_store)

    def consolidate(self) -> list[MemoryItem]:
        """Consolidate short-term observations with high importance or repeated occurrences into long-term memories."""
        short_term_items = self.memory_manager.store.list_all(memory_type=MemoryType.SHORT_TERM.value)
        consolidated = []

        for item in short_term_items:
            if item.importance >= 0.7:
                # Promote to LONG_TERM memory
                promoted = self.memory_manager.remember(
                    content=f"Consolidated knowledge: {item.content}",
                    memory_type=MemoryType.LONG_TERM.value,
                    tags=item.tags + ["consolidated"],
                    importance=item.importance,
                    source_run_id=item.source_run_id,
                )
                consolidated.append(promoted)

        return consolidated

    def resolve_strategy_conflict(
        self,
        existing_strategy_id: str,
        conflicting_rule: str,
        new_evidence: str,
    ) -> Optional[Strategy]:
        """Deterministically resolve a strategy conflict by versioning and superseding without erasing evidence history."""
        existing = self.strategy_store.get(existing_strategy_id)
        if not existing:
            return None

        # Record conflict evidence in old strategy
        existing.evidence.append(f"Conflict observed: {new_evidence}")
        existing.confidence = max(0.1, existing.confidence - 0.2)
        if existing.confidence <= 0.3:
            existing.status = StrategyStatus.WEAKENED.value
        self.strategy_store.update(existing)

        # Supersede with newer versioned strategy
        return self.evaluator.supersede_strategy(
            old_strategy_id=existing_strategy_id,
            new_rule=conflicting_rule,
            new_name=f"{existing.name} (Resolved Conflict)",
        )
