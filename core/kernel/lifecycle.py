# core/kernel/lifecycle.py
"""Kernel lifecycle — manages run lifecycle and state persistence."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core.config.storage import get_storage_dir
from core.kernel.schema import KernelContext, KernelStatus


def _gen_run_id() -> str:
    import time
    return f"KRUN-{int(time.time() * 1000) % 100000:05d}"


class KernelLifecycle:
    """Persist and recover kernel state.

    State stored at /root/agent-core/kernels/<run_id>.json
    Atomic writes.
    """

    def __init__(self, storage_dir: Optional[str] = None):
        if storage_dir is None:
            self._dir = get_storage_dir("kernels")
        else:
            self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, run_id: str) -> Path:
        return self._dir / f"{run_id}.json"

    def save(self, ctx: KernelContext) -> Path:
        """Atomic save."""
        target = self._path(ctx.run_id)
        tmp = target.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(ctx.to_dict(), f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
        return target

    def load(self, run_id: str) -> Optional[KernelContext]:
        path = self._path(run_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return KernelContext.from_dict(data)
        except (json.JSONDecodeError, KeyError, OSError):
            return None

    def exists(self, run_id: str) -> bool:
        return self._path(run_id).exists()

    def list_runs(self) -> list[str]:
        return sorted(p.stem for p in self._dir.glob("KRUN-*.json"))

    def delete(self, run_id: str) -> bool:
        path = self._path(run_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def mark_complete(self, ctx: KernelContext) -> KernelContext:
        ctx.kernel_status = KernelStatus.COMPLETED.value
        ctx.finished_at = ctx.now_str()
        self.save(ctx)
        return ctx

    def mark_failed(self, ctx: KernelContext, reason: str) -> KernelContext:
        ctx.kernel_status = KernelStatus.FAILED.value
        ctx.errors.append(reason)
        ctx.finished_at = ctx.now_str()
        self.save(ctx)
        return ctx

    def resume(self, run_id: str) -> Optional[KernelContext]:
        ctx = self.load(run_id)
        if not ctx:
            return None
        if ctx.kernel_status == KernelStatus.COMPLETED.value:
            return ctx  # already done
        ctx.kernel_status = KernelStatus.RESUMED.value
        self.save(ctx)
        return ctx
