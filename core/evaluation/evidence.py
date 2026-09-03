# core/evaluation/evidence.py
"""Evidence ledger for evaluation engine.

Same as knowledge provenance but for evaluation evidence.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional

from core.config.storage import get_storage_path
from core.evaluation.schema import Evidence, EvidenceType


_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
]


def _contains_secret(text: str) -> bool:
    for pat in _SECRET_PATTERNS:
        if pat.search(text):
            return True
    return False


class EvidenceLedger:
    """Persistent ledger of evaluation evidence.

    Stored at /root/agent-core/evaluation/evidence.json
    """

    def __init__(self, storage_path: Optional[str] = None):
        if storage_path is None:
            self._path = get_storage_path("evaluation/evidence.json")
        else:
            self._path = Path(storage_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._evidence: dict[str, Evidence] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for ev_dict in data.get("evidence", []):
                ev = Evidence.from_dict(ev_dict)
                self._evidence[ev.evidence_id] = ev
        except (json.JSONDecodeError, OSError, KeyError):
            pass

    def save(self) -> None:
        data = {"evidence": [ev.to_dict() for ev in self._evidence.values()]}
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self._path)

    def record(self, evidence: Evidence) -> Evidence:
        """Record evidence. Refuses secrets. Idempotent on evidence_id."""
        if not evidence.evidence_id:
            raise ValueError("evidence_id required")
        if _contains_secret(evidence.source + evidence.result + evidence.run_id):
            raise ValueError("Evidence contains secret-like content — refused")
        # Idempotent: same id → overwrite
        self._evidence[evidence.evidence_id] = evidence
        self.save()
        return evidence

    def get(self, evidence_id: str) -> Optional[Evidence]:
        return self._evidence.get(evidence_id)

    def all(self) -> list[Evidence]:
        return list(self._evidence.values())

    def filter(self, evidence_type: Optional[str] = None,
               run_id: Optional[str] = None) -> list[Evidence]:
        out = []
        for ev in self._evidence.values():
            if evidence_type and ev.type != evidence_type:
                continue
            if run_id and ev.run_id != run_id:
                continue
            out.append(ev)
        return out

    def count(self) -> int:
        return len(self._evidence)
