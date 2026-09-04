# core/learning/store.py
"""Strategy store — persistent filesystem store for Agent-Core strategies."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Optional

from core.config.storage import get_storage_dir
from core.learning.strategy import Strategy, StrategyStatus, StrategyApplication


class StrategyApplicationStore:
    """Atomic, JSON-backed filesystem storage for StrategyApplication records."""

    def __init__(self, store_dir: Optional[str] = None):
        if store_dir:
            self.store_dir = Path(store_dir)
        else:
            self.store_dir = get_storage_dir("strategy_applications")
        self.store_dir.mkdir(parents=True, exist_ok=True)

    def _file_path(self, application_id: str) -> Path:
        safe_id = "".join(c for c in application_id if c.isalnum() or c in ("-", "_"))
        return self.store_dir / f"{safe_id}.json"

    def create(self, app: StrategyApplication) -> StrategyApplication:
        p = self._file_path(app.application_id)
        data = {
            "application_id": app.application_id,
            "strategy_id": app.strategy_id,
            "run_id": app.run_id,
            "task_id": app.task_id,
            "context": dict(app.context),
            "expected_outcome": app.expected_outcome,
            "actual_outcome": app.actual_outcome,
            "verification_result": app.verification_result,
            "applied_at": app.applied_at,
        }
        self._write_atomic(p, data)
        return app

    def list_all(self, strategy_id: Optional[str] = None) -> list[StrategyApplication]:
        apps = []
        for p in self.store_dir.glob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    d = json.load(f)
                app = StrategyApplication(
                    application_id=d["application_id"],
                    strategy_id=d["strategy_id"],
                    run_id=d["run_id"],
                    task_id=d["task_id"],
                    context=dict(d.get("context", {})),
                    expected_outcome=d.get("expected_outcome", ""),
                    actual_outcome=d.get("actual_outcome", ""),
                    verification_result=d.get("verification_result", "PASS"),
                    applied_at=d.get("applied_at", ""),
                )
                if strategy_id is None or app.strategy_id == strategy_id:
                    apps.append(app)
            except (json.JSONDecodeError, OSError):
                continue
        apps.sort(key=lambda x: x.applied_at or "", reverse=True)
        return apps

    def _write_atomic(self, path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix="app_", suffix=".tmp")
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


class StrategyStore:
    """Atomic, JSON-backed filesystem storage for Strategy objects."""

    def __init__(self, store_dir: Optional[str] = None):
        if store_dir:
            self.store_dir = Path(store_dir)
        else:
            self.store_dir = get_storage_dir("strategies")
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, Strategy] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        self._cache.clear()
        for p in self.store_dir.glob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                strat = Strategy.from_dict(data)
                self._cache[strat.strategy_id] = strat
            except (json.JSONDecodeError, OSError):
                continue

    def _file_path(self, strategy_id: str) -> Path:
        safe_id = "".join(c for c in strategy_id if c.isalnum() or c in ("-", "_"))
        return self.store_dir / f"{safe_id}.json"

    def create(self, strategy: Strategy) -> Strategy:
        p = self._file_path(strategy.strategy_id)
        if p.exists() or strategy.strategy_id in self._cache:
            raise ValueError(f"Strategy already exists: {strategy.strategy_id}")
        self._write_atomic(p, strategy.to_dict())
        self._cache[strategy.strategy_id] = strategy
        return strategy

    def update(self, strategy: Strategy) -> Strategy:
        p = self._file_path(strategy.strategy_id)
        strategy.touch()
        self._write_atomic(p, strategy.to_dict())
        self._cache[strategy.strategy_id] = strategy
        return strategy

    def get(self, strategy_id: str) -> Optional[Strategy]:
        if strategy_id in self._cache:
            return self._cache[strategy_id]
        p = self._file_path(strategy_id)
        if not p.exists():
            return None
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            strat = Strategy.from_dict(data)
            self._cache[strat.strategy_id] = strat
            return strat
        except (json.JSONDecodeError, OSError):
            return None

    def delete(self, strategy_id: str) -> bool:
        self._cache.pop(strategy_id, None)
        p = self._file_path(strategy_id)
        if p.exists():
            try:
                p.unlink()
                return True
            except OSError:
                return False
        return False

    def list_all(self, status: Optional[str] = None) -> list[Strategy]:
        strategies = [
            s for s in self._cache.values()
            if status is None or s.status == status
        ]
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
