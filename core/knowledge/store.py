# core/knowledge/store.py
"""Atomic, corruption-resistant primitive store.

Design:
    - One JSON file per primitive: <store_dir>/<id>.json
    - Atomic write: write tmp → fsync → os.replace
    - Index: <store_dir>/index.json (id → path mapping)
    - Schema-version stamped on every primitive
    - Duplicate IDs rejected
    - Detect-and-recover from corruption (skip unreadable files)
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Optional

from core.config.storage import get_storage_dir
from core.knowledge.schema import Primitive, generate_primitive_id


class StoreError(ValueError):
    pass


class PrimitiveStore:
    """Persistent atomic store for primitives.

    All files are stored under <store_dir>/. The store is intentionally
    backend-agnostic: any directory-like backend can be plugged in.
    """

    SCHEMA_VERSION = 1

    def __init__(self, store_dir: Optional[str] = None):
        if store_dir is None:
            self._dir = get_storage_dir("knowledge")
        else:
            self._dir = Path(store_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._dir / "index.json"

    # ── Paths ────────────────────────────────────────────────────────

    def _path(self, prim_id: str) -> Path:
        return self._dir / f"{prim_id}.json"

    def _tmp_path(self, prim_id: str) -> Path:
        return self._dir / f"{prim_id}.json.tmp"

    # ── Index ────────────────────────────────────────────────────────

    def _load_index(self) -> dict:
        if not self._index_path.exists():
            return {"version": self.SCHEMA_VERSION, "primitives": {}}
        try:
            with open(self._index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"version": self.SCHEMA_VERSION, "primitives": {}}

    def _save_index(self, idx: dict) -> None:
        tmp = self._index_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(idx, f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self._index_path)

    def _update_index(self, prim_id: str, action: str) -> None:
        """action in {add, remove}"""
        idx = self._load_index()
        if action == "add":
            idx["primitives"][prim_id] = prim_id
        elif action == "remove":
            idx["primitives"].pop(prim_id, None)
        self._save_index(idx)

    # ── CRUD ─────────────────────────────────────────────────────────

    def create(self, prim: Primitive) -> Primitive:
        """Persist a new primitive. Raises StoreError on duplicate."""
        if not prim.id:
            prim.id = generate_primitive_id()
        if self.exists(prim.id):
            raise StoreError(f"Duplicate primitive id: {prim.id}")

        # Stamp timestamps
        if not prim.created_at:
            prim.created_at = prim.now_str()
        prim.updated_at = prim.now_str()
        prim.schema_version = self.SCHEMA_VERSION

        self._atomic_write(prim)
        self._update_index(prim.id, "add")
        return prim

    def update(self, prim: Primitive) -> Primitive:
        """Overwrite an existing primitive. Raises StoreError if missing."""
        if not self.exists(prim.id):
            raise StoreError(f"Primitive not found: {prim.id}")
        prim.updated_at = prim.now_str()
        prim.version += 1
        self._atomic_write(prim)
        return prim

    def get(self, prim_id: str) -> Optional[Primitive]:
        """Load a primitive by id. Returns None if missing or corrupt."""
        path = self._path(prim_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            prim = Primitive.from_dict(data)
            # Auto-migrate if needed
            if prim.schema_version < self.SCHEMA_VERSION:
                prim = self.migrate(prim)
            return prim
        except (json.JSONDecodeError, KeyError, TypeError, OSError):
            return None

    def delete(self, prim_id: str) -> bool:
        path = self._path(prim_id)
        if path.exists():
            path.unlink()
            self._update_index(prim_id, "remove")
            return True
        return False

    def exists(self, prim_id: str) -> bool:
        return self._path(prim_id).exists()

    def list_all(self) -> list[Primitive]:
        """Load every primitive. Corrupt files are skipped (reported as count)."""
        result: list[Primitive] = []
        idx = self._load_index()
        for pid in idx.get("primitives", {}).keys():
            prim = self.get(pid)
            if prim is not None:
                result.append(prim)
        return result

    def list_ids(self) -> list[str]:
        return sorted(self._load_index().get("primitives", {}).keys())

    def count(self) -> int:
        return len(self._load_index().get("primitives", {}))

    # ── Atomic write ────────────────────────────────────────────────

    def _atomic_write(self, prim: Primitive) -> None:
        target = self._path(prim.id)
        tmp = self._tmp_path(prim.id)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(prim.to_dict(), f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)

    # ── Migration ───────────────────────────────────────────────────

    def migrate(self, prim: Primitive) -> Primitive:
        """Forward-migrate a primitive to current SCHEMA_VERSION.

        Idempotent: applying twice is a no-op.
        """
        if prim.schema_version >= self.SCHEMA_VERSION:
            return prim
        # v0 -> v1: nothing structural changed, but ensure all fields present
        if prim.schema_version < 1:
            if not prim.provenance.source_type:
                prim.provenance.source_type = "manual"
            if not prim.provenance.created_by:
                prim.provenance.created_by = "agent-core"
        prim.schema_version = self.SCHEMA_VERSION
        return prim
