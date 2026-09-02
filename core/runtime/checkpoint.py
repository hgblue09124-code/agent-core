# core/runtime/checkpoint.py
"""Atomic durable checkpoint persistence.

Strategy:
    1. Write to <file>.tmp
    2. fsync the file
    3. atomic os.replace(<file>.tmp, <file>)
If the process dies at any point, either the old valid file or the new
valid file is on disk — never a half-written one.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Optional

from core.runtime.schema import RunState


class CheckpointStore:
    """Persists and retrieves RunState as JSON files in <runs_dir>/."""

    def __init__(self, runs_dir: Optional[str] = None):
        if runs_dir is None:
            self._dir = Path("/root/agent-core/runs")
        else:
            self._dir = Path(runs_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    # ── Paths ────────────────────────────────────────────────────────

    def _path(self, run_id: str) -> Path:
        return self._dir / f"{run_id}.json"

    def _tmp_path(self, run_id: str) -> Path:
        return self._dir / f"{run_id}.json.tmp"

    # ── Write ────────────────────────────────────────────────────────

    def save(self, state: RunState) -> Path:
        """Atomic write: tmp → fsync → replace.

        Returns the path to the final file.
        """
        target = self._path(state.run_id)
        tmp = self._tmp_path(state.run_id)

        # Write to tmp file in same dir (so os.replace is atomic on POSIX)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())

        # Atomic rename
        os.replace(tmp, target)
        return target

    # ── Read ─────────────────────────────────────────────────────────

    def load(self, run_id: str) -> Optional[RunState]:
        """Load a run state. Returns None if not found or corrupted.

        If the main file is missing but a .tmp exists (interrupted write),
        the .tmp is treated as corrupted and ignored.
        """
        path = self._path(run_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return RunState.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def exists(self, run_id: str) -> bool:
        return self._path(run_id).exists()

    def list_runs(self) -> list[str]:
        return sorted(p.stem for p in self._dir.glob("RUN-*.json"))

    def delete(self, run_id: str) -> bool:
        path = self._path(run_id)
        if path.exists():
            path.unlink()
            return True
        return False
