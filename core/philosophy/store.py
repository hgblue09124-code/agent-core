# core/philosophy/store.py
"""Atomic persistent store for philosophy tendencies.

Design:
- One JSON file per tendency: <store_dir>/<tendency_id>.json
- Atomic write: write tmp → fsync → os.replace
- Index: <store_dir>/index.json (tendency_id → path mapping)
- Persistence root defaults to get_storage_dir('philosophy')
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from core.config.storage import get_storage_dir
from core.philosophy.schema import PhilosophyTendency


class PhilosophyStoreError(ValueError):
    pass


class PhilosophyStore:
    """Atomic persistent store for philosophy tendencies."""

    SCHEMA_VERSION = 1

    def __init__(self, store_dir: Optional[str] = None):
        if store_dir is None:
            self._dir = get_storage_dir("philosophy")
        else:
            self._dir = Path(store_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._dir / "index.json"

    def _path(self, tendency_id: str) -> Path:
        return self._dir / f"{tendency_id}.json"

    def _tmp_path(self, tendency_id: str) -> Path:
        return self._dir / f"{tendency_id}.json.tmp"

    def _load_index(self) -> dict:
        if not self._index_path.exists():
            return {"version": self.SCHEMA_VERSION, "tendencies": {}}
        try:
            with open(self._index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"version": self.SCHEMA_VERSION, "tendencies": {}}

    def _save_index(self, idx: dict) -> None:
        tmp = self._index_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(idx, f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self._index_path)

    def _update_index(self, tendency_id: str, action: str) -> None:
        idx = self._load_index()
        if action == "add":
            idx["tendencies"][tendency_id] = tendency_id
        elif action == "remove":
            idx["tendencies"].pop(tendency_id, None)
        self._save_index(idx)

    def save(self, tendency: PhilosophyTendency) -> PhilosophyTendency:
        """Persist or update a philosophy tendency atomically."""
        if not tendency.tendency_id:
            raise PhilosophyStoreError("tendency_id is required")

        self._atomic_write(tendency)
        self._update_index(tendency.tendency_id, "add")
        return tendency

    def get(self, tendency_id: str) -> Optional[PhilosophyTendency]:
        path = self._path(tendency_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return PhilosophyTendency.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError, OSError):
            return None

    def exists(self, tendency_id: str) -> bool:
        return self._path(tendency_id).exists()

    def list_all(self) -> list[PhilosophyTendency]:
        result: list[PhilosophyTendency] = []
        idx = self._load_index()
        for tid in idx.get("tendencies", {}).keys():
            t = self.get(tid)
            if t is not None:
                result.append(t)
        return result

    def delete(self, tendency_id: str) -> bool:
        path = self._path(tendency_id)
        if path.exists():
            path.unlink()
            self._update_index(tendency_id, "remove")
            return True
        return False

    def count(self) -> int:
        return len(self._load_index().get("tendencies", {}))

    def _atomic_write(self, tendency: PhilosophyTendency) -> None:
        target = self._path(tendency.tendency_id)
        tmp = self._tmp_path(tendency.tendency_id)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(tendency.to_dict(), f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
