# core/knowledge/provenance.py
"""Provenance tracker — links primitives to evidence to runs/tasks/verifications.

Every primitive records HOW it came into being. This module gives
the kernel a way to:
    1. Record evidence for a primitive
    2. Look up which primitives are linked to a run/task
    3. Verify chain: primitive → evidence → run → task
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
]


@dataclass
class Evidence:
    """A single evidence record.

    `fingerprint` is an optional short hash for content fingerprinting.
    `source` describes where the evidence came from (test, command, etc.).
    """
    evidence_id: str
    type: str        # test | command_result | file_state | checkpoint | manual | observation
    source: str
    result: str
    timestamp: str = ""
    fingerprint: str = ""
    run_id: str = ""
    task_id: str = ""

    def to_dict(self) -> dict:
        return {
            "evidence_id": self.evidence_id,
            "type": self.type,
            "source": self.source,
            "result": self.result,
            "timestamp": self.timestamp,
            "fingerprint": self.fingerprint,
            "run_id": self.run_id,
            "task_id": self.task_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Evidence":
        return cls(
            evidence_id=d["evidence_id"],
            type=d.get("type", "manual"),
            source=d.get("source", ""),
            result=d.get("result", ""),
            timestamp=d.get("timestamp", ""),
            fingerprint=d.get("fingerprint", ""),
            run_id=d.get("run_id", ""),
            task_id=d.get("task_id", ""),
        )

    def contains_secret(self) -> bool:
        blob = " ".join([self.source, self.result, self.run_id, self.task_id])
        for pat in _SECRET_PATTERNS:
            if pat.search(blob):
                return True
        return False


from core.config.storage import get_storage_path


class ProvenanceTracker:
    """In-memory evidence ledger.

    Backed by a single JSON file. Atomic writes.
    """

    def __init__(self, storage_path: Optional[str] = None):
        if storage_path is None:
            self._path = get_storage_path("knowledge/evidence.json")
        else:
            self._path = __import__("pathlib").Path(storage_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._evidence: dict[str, Evidence] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        import json
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for ev_dict in data.get("evidence", []):
                ev = Evidence.from_dict(ev_dict)
                self._evidence[ev.evidence_id] = ev
        except (json.JSONDecodeError, OSError, KeyError):
            pass

    def save(self) -> None:
        """Atomic save."""
        import json, os
        data = {"evidence": [ev.to_dict() for ev in self._evidence.values()]}
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self._path)

    def record(self, evidence: Evidence) -> Evidence:
        """Record a new evidence. Refuses secrets."""
        if evidence.contains_secret():
            raise ValueError("Evidence contains secret-like content — refused")
        if not evidence.timestamp:
            evidence.timestamp = datetime.now(timezone.utc).isoformat()
        self._evidence[evidence.evidence_id] = evidence
        self.save()
        return evidence

    def get(self, evidence_id: str) -> Optional[Evidence]:
        return self._evidence.get(evidence_id)

    def find_by_run(self, run_id: str) -> list[Evidence]:
        return [ev for ev in self._evidence.values() if ev.run_id == run_id]

    def find_by_task(self, task_id: str) -> list[Evidence]:
        return [ev for ev in self._evidence.values() if ev.task_id == task_id]

    def all(self) -> list[Evidence]:
        return list(self._evidence.values())
