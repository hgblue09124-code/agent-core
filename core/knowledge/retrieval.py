# core/knowledge/retrieval.py
"""Deterministic retrieval engine for knowledge primitives.

Pipeline:
    1. Build the candidate set (index filter)
    2. Score each candidate with the ranker
    3. Expand via relation graph (bounded)
    4. Return top-K with explainable reasons
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core.knowledge.index import InvertedIndex
from core.knowledge.ranking import Ranker, Score
from core.knowledge.relations import RelationGraph
from core.knowledge.schema import Primitive


@dataclass
class RetrievalResult:
    query: str
    domain: Optional[str]
    top_k: int
    scores: list[Score] = field(default_factory=list)
    expanded_ids: list[str] = field(default_factory=list)
    candidates_considered: int = 0

    @property
    def ids(self) -> list[str]:
        return [s.primitive_id for s in self.scores]


class RetrievalEngine:
    """Coordinates index → ranker → graph expansion."""

    def __init__(self, primitives: list[Primitive],
                 index: Optional[InvertedIndex] = None,
                 graph: Optional[RelationGraph] = None):
        self._primitives: dict[str, Primitive] = {p.id: p for p in primitives}
        self._index = index or InvertedIndex()
        if primitives:
            self._index.rebuild_from_primitives(primitives)
        self._graph = graph or RelationGraph()
        self._graph.load_from_store(list(self._primitives.values()))
        self._ranker = Ranker()

    def update(self, prim: Primitive) -> None:
        """Update a single primitive in memory and indexes."""
        self._primitives[prim.id] = prim
        self._index.add(prim)
        self._graph.add_primitive(prim)

    def refresh(self, primitives: list[Primitive]) -> None:
        """Replace the entire in-memory view."""
        self._primitives = {p.id: p for p in primitives}
        self._index.rebuild_from_primitives(primitives)
        self._graph.load_from_store(primitives)

    def retrieve(self, query: str, domain: Optional[str] = None,
                 top_k: int = 5,
                 expand_depth: int = 0) -> RetrievalResult:
        """Retrieve and rank primitives for a query.

        Args:
            query: Free text query.
            domain: Optional domain filter.
            top_k: Number of top results to return.
            expand_depth: How many hops to expand via relations.
        """
        # 1. Candidate set from index
        candidates: list[Primitive] = []
        seen: set[str] = set()

        # Use index for fast filter
        try:
            for pid, _ in self._index.search(query, domain=domain):
                if pid not in seen and pid in self._primitives:
                    candidates.append(self._primitives[pid])
                    seen.add(pid)
        except Exception:
            pass

        # If index missed, fall back to scanning
        if not candidates:
            q_lower = query.lower()
            for pid, prim in self._primitives.items():
                if pid in seen:
                    continue
                if (q_lower in prim.concept.lower()
                        or q_lower in prim.description.lower()
                        or q_lower in prim.when_to_use.lower()):
                    candidates.append(prim)
                    seen.add(pid)

        # 2. Rank
        scores = self._ranker.rank(query, candidates, domain=domain, top_k=top_k)

        # 3. Expand via relations
        expanded: list[str] = []
        if expand_depth > 0:
            for s in scores:
                related = self._graph.get_related(s.primitive_id, max_depth=expand_depth)
                for rid in related:
                    if rid not in seen:
                        expanded.append(rid)
                        seen.add(rid)

        return RetrievalResult(
            query=query,
            domain=domain,
            top_k=top_k,
            scores=scores,
            expanded_ids=expanded,
            candidates_considered=len(candidates),
        )

    def get(self, prim_id: str) -> Optional[Primitive]:
        return self._primitives.get(prim_id)
