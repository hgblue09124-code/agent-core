# core/knowledge/index.py
"""Inverted index for fast keyword retrieval.

Maintains:
    term -> [primitive_id, ...]
    domain -> [primitive_id, ...]
    status -> [primitive_id, ...]

No embeddings needed. Pure inverted index.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional

from core.config.storage import get_storage_path
from core.knowledge.schema import Primitive, KnowledgeStatus


_MIN_TOKEN_LEN = 2


def _tokens(text: str) -> set[str]:
    if not text:
        return set()
    return {t.lower() for t in re.findall(r"[A-Za-z0-9_]+", text) if len(t) >= _MIN_TOKEN_LEN}


class InvertedIndex:
    """In-memory inverted index, backed by a JSON file.

    Rebuild with `rebuild()`, persist with `save()`.
    """

    def __init__(self, index_path: Optional[str] = None):
        if index_path:
            self._path = Path(index_path)
        else:
            self._path = get_storage_path("knowledge/index.json")
        self._term_index: dict[str, set[str]] = {}   # term -> set of prim ids
        self._domain_index: dict[str, set[str]] = {}  # domain -> set of prim ids
        self._status_index: dict[str, set[str]] = {}  # status -> set of prim ids
        self._all_ids: set[str] = set()

    def add(self, prim: Primitive) -> None:
        """Add a primitive to the index."""
        self._all_ids.add(prim.id)

        # Term index
        for token in _tokens(prim.concept):
            self._term_index.setdefault(token, set()).add(prim.id)
        for token in _tokens(prim.description):
            self._term_index.setdefault(token, set()).add(prim.id)
        for token in _tokens(prim.when_to_use):
            self._term_index.setdefault(token, set()).add(prim.id)
        for token in _tokens(prim.domain):
            self._term_index.setdefault(token, set()).add(prim.id)

        # Domain index
        self._domain_index.setdefault(prim.domain, set()).add(prim.id)

        # Status index
        self._status_index.setdefault(prim.status, set()).add(prim.id)

    def remove(self, prim_id: str, prim: Optional[Primitive] = None) -> None:
        """Remove a primitive from the index."""
        if prim_id not in self._all_ids:
            return
        self._all_ids.discard(prim_id)
        # Rebuild the affected token entries
        self.rebuild_from_primitives([])

    def search(self, query: str, domain: Optional[str] = None,
               status: Optional[str] = None,
               min_score: float = 0) -> list[tuple[str, float]]:
        """Fast keyword search. Returns [(prim_id, match_score), ...]."""
        query_tokens = _tokens(query)
        if not query_tokens:
            return []
        result_ids: dict[str, float] = {}
        for token in query_tokens:
            if token in self._term_index:
                for pid in self._term_index[token]:
                    result_ids[pid] = result_ids.get(pid, 0.0) + 1.0

        # Domain filter
        if domain:
            if domain in self._domain_index:
                result_ids = {k: v for k, v in result_ids.items() if k in self._domain_index[domain]}
            else:
                return []

        # Status filter
        if status:
            if status in self._status_index:
                result_ids = {k: v for k, v in result_ids.items() if k in self._status_index[status]}
            else:
                return []

        # Filter by min_score (token overlap ratio)
        if min_score > 0:
            result_ids = {k: v for k, v in result_ids.items() if v >= min_score}

        return sorted(result_ids.items(), key=lambda x: (-x[1], x[0]))

    def rebuild_from_primitives(self, prims: list[Primitive]) -> None:
        """Rebuild the entire index from a list of primitives."""
        self._term_index.clear()
        self._domain_index.clear()
        self._status_index.clear()
        self._all_ids.clear()
        for prim in prims:
            self.add(prim)

    def save(self) -> None:
        """Persist index to disk atomically."""
        data = {
            "term_index": {k: list(v) for k, v in self._term_index.items()},
            "domain_index": {k: list(v) for k, v in self._domain_index.items()},
            "status_index": {k: list(v) for k, v in self._status_index.items()},
            "all_ids": list(self._all_ids),
        }
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self._path)

    def load(self) -> bool:
        """Load index from disk. Returns False if not found."""
        if not self._path.exists():
            return False
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._term_index = {k: set(v) for k, v in data.get("term_index", {}).items()}
            self._domain_index = {k: set(v) for k, v in data.get("domain_index", {}).items()}
            self._status_index = {k: set(v) for k, v in data.get("status_index", {}).items()}
            self._all_ids = set(data.get("all_ids", []))
            return True
        except (json.JSONDecodeError, OSError):
            return False

    def count(self) -> int:
        return len(self._all_ids)
