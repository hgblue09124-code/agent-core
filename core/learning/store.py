# core/learning/store.py
"""Strategy store — persistent filesystem store for Agent-Core strategies."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Optional

from core.config.storage import get_storage_dir
from core.learning.strategy import Strategy, StrategyStatus


class StrategyStore:
    """Atomic, JSON-backed filesystem storage for Strategy objects."""

    def __init__(self, store_dir: Optional[str] = None):
        if store_dir:
            self.store_dir = Path(store_dir)
        else:
            self.store_dir = get_storage_dir("strategies")
        self.store_dir.mkdir(parents=True, exist_ok=True)

    def _file_path(self, strategy_id: str) -> Path:
        safe_id = "".join(c for c in strategy_id if c.isalnum() or c in ("-", "_"))
        return self.store_dir / f"{safe_id}.json"

    def create(self, strategy: Strategy) -> Strategy:
        p = self._file_path(strategy.strategy_id)
        if p.exists():
            raise ValueError(f"Strategy already exists: {strategy.strategy_id}")
        self._write_atomic(p, strategy.to_dict())
        return strategy

    def update(self, strategy: Strategy) -> Strategy:
        p = self._file_path(strategy.strategy_id)
        strategy.touch()
        self._write_atomic(p, strategy.to_dict())
        return strategy

    def get(self, strategy_id: str) -> Optional[Strategy]:
        p = self._file_path(strategy_id)
        if not p.exists():
            return None
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Strategy.from_dict(data)
        except (json.JSONDecodeError, OSError):
            return None

    def delete(self, strategy_id: str) -> bool:
        p = self._file_path(strategy_id)
        if p.exists():
            try:
                p.unlink()
                return True
            except OSError:
                return False
        return False

    def list_all(self, status: Optional[str] = None) -> list[Strategy]:
        strategies = []
        for p in self.store_dir.glob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                strat = Strategy.from_dict(data)
                if status is None or strat.status == status:
                    strategies.append(strat)
            except (json.JSONDecodeError, OSError):
                continue
        strategies.sort(key=lambda x: (x.confidence, x.updated_at or x.created_at or ""), reverse=True)
        return strategies

    def _write_atomic(self, path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix="strat_", suffix=".tmp")
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
