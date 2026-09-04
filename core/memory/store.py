# core/memory/store.py
"""Memory store — persistent filesystem store for Agent-Core memory items."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Optional

from core.config.storage import get_storage_dir
from core.memory.schema import MemoryItem


class MemoryStore:
    """Atomic, JSON-backed filesystem storage for memory items."""

    def __init__(self, store_dir: Optional[str] = None):
        if store_dir:
            self.store_dir = Path(store_dir)
        else:
            self.store_dir = get_storage_dir("memory")
        self.store_dir.mkdir(parents=True, exist_ok=True)

    def _file_path(self, memory_id: str) -> Path:
        safe_id = "".join(c for c in memory_id if c.isalnum() or c in ("-", "_"))
        return self.store_dir / f"{safe_id}.json"

    def create(self, item: MemoryItem) -> MemoryItem:
        p = self._file_path(item.memory_id)
        if p.exists():
            raise ValueError(f"MemoryItem already exists: {item.memory_id}")
        self._write_atomic(p, item.to_dict())
        return item

    def update(self, item: MemoryItem) -> MemoryItem:
        p = self._file_path(item.memory_id)
        item.touch()
        self._write_atomic(p, item.to_dict())
        return item

    def get(self, memory_id: str) -> Optional[MemoryItem]:
        p = self._file_path(memory_id)
        if not p.exists():
            return None
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            return MemoryItem.from_dict(data)
        except (json.JSONDecodeError, OSError):
            return None

    def delete(self, memory_id: str) -> bool:
        p = self._file_path(memory_id)
        if p.exists():
            try:
                p.unlink()
                return True
            except OSError:
                return False
        return False

    def list_all(self, memory_type: Optional[str] = None) -> list[MemoryItem]:
        items = []
        for p in self.store_dir.glob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                item = MemoryItem.from_dict(data)
                if memory_type is None or item.memory_type == memory_type:
                    items.append(item)
            except (json.JSONDecodeError, OSError):
                continue
        items.sort(key=lambda x: x.created_at or "", reverse=True)
        return items

    def _write_atomic(self, path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix="mem_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except Exception:
            if os.path.exists(tmp):
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
            raise
