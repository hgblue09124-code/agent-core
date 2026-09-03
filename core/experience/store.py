# core/experience/store.py
"""Atomic, append-only experience store.

Design:
    - One JSON file per experience: <store_dir>/<run_id>.json
    - Atomic write: write tmp → fsync → os.replace
    - Index: <store_dir>/index.json (run_id → path mapping)
    - Append-only: experiences are never updated, only added
    - Corruption detection: corrupt files are skipped on load
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from core.experience.schema import Experience


class ExperienceStoreError(ValueError):
    pass


class ExperienceStore:
    """Persistent append-only store for experiences."""

    SCHEMA_VERSION = 1

    def __init__(self, store_dir: Optional[str] = None):
        if store_dir is None:
            self._dir = Path("/root/agent-core/experience")
        else:
            self._dir = Path(store_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._dir / "index.json"

    def _path(self, run_id: str) -> Path:
        return self._dir / f"{run_id}.json"

    def _tmp_path(self, run_id: str) -> Path:
        return self._dir / f"{run_id}.json.tmp"

    def _load_index(self) -> dict:
        if not self._index_path.exists():
            return {"version": self.SCHEMA_VERSION, "experiences": {}}
        try:
            with open(self._index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"version": self.SCHEMA_VERSION, "experiences": {}}

    def _save_index(self, idx: dict) -> None:
        tmp = self._index_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(idx, f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self._index_path)

    def _update_index(self, run_id: str, action: str) -> None:
        idx = self._load_index()
        if action == "add":
            idx["experiences"][run_id] = run_id
        elif action == "remove":
            idx["experiences"].pop(run_id, None)
        self._save_index(idx)

    def create(self, exp: Experience) -> Experience:
        """Persist a new experience. Raises on duplicate."""
        if not exp.run_id:
            raise ExperienceStoreError("run_id is required")
        if self.exists(exp.run_id):
            raise ExperienceStoreError(f"Duplicate experience: {exp.run_id}")
        if not exp.created_at:
            exp.created_at = exp.now_str()
        exp.schema_version = self.SCHEMA_VERSION
        self._atomic_write(exp)
        self._update_index(exp.run_id, "add")
        return exp

    def get(self, run_id: str) -> Optional[Experience]:
        path = self._path(run_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            exp = Experience.from_dict(data)
            if exp.schema_version < self.SCHEMA_VERSION:
                exp = self.migrate(exp)
            return exp
        except (json.JSONDecodeError, KeyError, TypeError, OSError):
            return None

    def exists(self, run_id: str) -> bool:
        return self._path(run_id).exists()

    def list_all(self) -> list[Experience]:
        result: list[Experience] = []
        idx = self._load_index()
        for rid in idx.get("experiences", {}).keys():
            exp = self.get(rid)
            if exp is not None:
                result.append(exp)
        return result

    def list_ids(self) -> list[str]:
        return sorted(self._load_index().get("experiences", {}).keys())

    def count(self) -> int:
        return len(self._load_index().get("experiences", {}))

    def delete(self, run_id: str) -> bool:
        path = self._path(run_id)
        if path.exists():
            path.unlink()
            self._update_index(run_id, "remove")
            return True
        return False

    def _atomic_write(self, exp: Experience) -> None:
        target = self._path(exp.run_id)
        tmp = self._tmp_path(exp.run_id)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(exp.to_dict(), f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)

    def migrate(self, exp: Experience) -> Experience:
        if exp.schema_version >= self.SCHEMA_VERSION:
            return exp
        exp.schema_version = self.SCHEMA_VERSION
        return exp
