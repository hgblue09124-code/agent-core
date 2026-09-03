# core/knowledge/relations.py
"""Typed relation graph for primitives.

Supports:
    - typed edges (e.g. REQUIRES, ALTERNATIVE_TO)
    - self-loop prevention
    - antisymmetric validation
    - bounded depth traversal
    - duplicate edge prevention
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Optional

from core.knowledge.schema import Relation, RelationType, Primitive


class RelationError(ValueError):
    pass


# Relations that do NOT allow self-loops
_NO_SELF_LOOP_TYPES = {
    RelationType.REQUIRES,
    RelationType.ALTERNATIVE_TO,
    RelationType.IMPROVES,
    RelationType.DEPENDS_ON,
    RelationType.CONFLICTS_WITH,
    RelationType.COMMONLY_FAILS_WITH,
    RelationType.DERIVED_FROM,
    RelationType.SUPERSEDES,
}

# Antisymmetric: if A -> B, then B -> A is illegal
_ANTISYMMETRIC = {
    RelationType.REQUIRES,
    RelationType.DEPENDS_ON,
    RelationType.IMPROVES,
    RelationType.DERIVED_FROM,
    RelationType.SUPERSEDES,
}


@dataclass
class RelationGraph:
    """In-memory relation graph backed by a store of primitives.

    All mutations are validated before application.
    """
    primitives: dict[str, Primitive] = field(default_factory=dict)

    # ── Building ─────────────────────────────────────────────────────

    def add_primitive(self, prim: Primitive) -> None:
        self.primitives[prim.id] = prim

    def load_from_store(self, prims: list[Primitive]) -> None:
        self.primitives = {p.id: p for p in prims}

    # ── Edge validation ───────────────────────────────────────────────

    def _validate_edge(self, source_id: str, rel: Relation) -> Relation:
        """Validate and normalise an edge. Raises RelationError on failure."""
        target_id = rel.target_id

        # Source must exist
        if source_id not in self.primitives:
            raise RelationError(f"Source primitive not found: {source_id}")

        # Target must exist
        if target_id not in self.primitives:
            raise RelationError(f"Target primitive not found: {target_id}")

        # Relation type must be valid
        try:
            rtype = RelationType(rel.relation_type)
        except ValueError:
            raise RelationError(f"Unknown relation type: {rel.relation_type}")

        # Self-loop check
        if source_id == target_id and rtype in _NO_SELF_LOOP_TYPES:
            raise RelationError(
                f"Self-loop not allowed for relation type {rtype.value}"
            )

        # Antisymmetric check
        if rtype in _ANTISYMMETRIC:
            existing = self.primitives[source_id].relations
            if any(r.target_id == target_id and r.relation_type == rel.relation_type for r in existing):
                raise RelationError(
                    f"Duplicate edge: {source_id} --{rel.relation_type}--> {target_id}"
                )
            # Check reverse doesn't exist
            target_prim = self.primitives[target_id]
            if any(r.target_id == source_id and r.relation_type == rel.relation_type for r in target_prim.relations):
                raise RelationError(
                    f"Antisymmetric conflict: both {source_id} → {target_id} and {target_id} → {source_id} with {rel.relation_type}"
                )

        return rel

    # ── Mutations ─────────────────────────────────────────────────────

    def add_relation(self, source_id: str, rel: Relation) -> None:
        """Add a validated relation to a primitive."""
        validated = self._validate_edge(source_id, rel)
        prim = self.primitives[source_id]
        # Prevent duplicate
        if not any(r.target_id == validated.target_id and r.relation_type == validated.relation_type for r in prim.relations):
            prim.relations.append(validated)

    def remove_relation(self, source_id: str, target_id: str,
                       relation_type: str) -> bool:
        """Remove a relation. Returns True if found and removed."""
        if source_id not in self.primitives:
            return False
        prim = self.primitives[source_id]
        original = len(prim.relations)
        prim.relations = [
            r for r in prim.relations
            if not (r.target_id == target_id and r.relation_type == relation_type)
        ]
        return len(prim.relations) < original

    # ── Traversal ─────────────────────────────────────────────────────

    def expand(self, start_id: str, max_depth: int = 2) -> list[tuple[str, str, int]]:
        """Return all reachable (primitive_id, relation_type, depth) from start.

        Depth 0 = the start primitive itself.
        Depth 1 = direct neighbours.
        Depth 2 = neighbours of neighbours.
        """
        if start_id not in self.primitives:
            return []
        result: list[tuple[str, str, int]] = []
        visited: set[str] = set()
        queue: list[tuple[str, int]] = [(start_id, 0)]

        while queue:
            current_id, depth = queue.pop(0)
            if current_id in visited or depth > max_depth:
                continue
            visited.add(current_id)
            result.append((current_id, "", depth))

            if depth >= max_depth:
                continue
            prim = self.primitives.get(current_id)
            if prim:
                for rel in prim.relations:
                    if rel.target_id not in visited:
                        result.append((rel.target_id, rel.relation_type, depth + 1))
                        queue.append((rel.target_id, depth + 1))
        return result

    def get_related(self, prim_id: str,
                    relation_type: Optional[str] = None,
                    max_depth: int = 1) -> list[str]:
        """Get all primitive IDs reachable from prim_id within max_depth hops."""
        if relation_type:
            return [
                pid for pid, rtype, depth in self.expand(prim_id, max_depth)
                if pid != prim_id and rtype == relation_type
            ]
        return [
            pid for pid, _, depth in self.expand(prim_id, max_depth)
            if pid != prim_id
        ]

    def get_relation_types(self, source_id: str,
                           target_id: str) -> list[str]:
        """Get all relation types between source and target."""
        if source_id not in self.primitives:
            return []
        return [
            r.relation_type
            for r in self.primitives[source_id].relations
            if r.target_id == target_id
        ]

    def find_cycles(self) -> list[list[str]]:
        """Detect all cycles in the graph using DFS.

        Only detects cycles through DEPENDS_ON / REQUIRES edges.
        """
        cycles: list[list[str]] = []
        visited: set[str] = set()
        path: list[str] = []

        def dfs(node: str) -> None:
            visited.add(node)
            path.append(node)
            prim = self.primitives.get(node)
            if prim:
                for rel in prim.relations:
                    if rel.relation_type in (RelationType.DEPENDS_ON.value, RelationType.REQUIRES.value):
                        if rel.target_id not in visited:
                            dfs(rel.target_id)
                        elif rel.target_id in path:
                            idx = path.index(rel.target_id)
                            cycles.append(path[idx:] + [rel.target_id])
            path.pop()

        for pid in self.primitives:
            if pid not in visited:
                dfs(pid)
        return cycles
