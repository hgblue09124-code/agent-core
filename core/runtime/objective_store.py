# core/runtime/objective_store.py
"""ObjectiveStore — persistent Objective lifecycle. Runtime-owned."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Optional

from core.config.storage import get_storage_dir
from core.runtime.classify import GoalIntent, classify_goal
from core.runtime.models import (
    OPEN_OBJECTIVE_STATES,
    Objective,
    ObjectiveKind,
    ObjectiveState,
    RuntimeEvent,
    RuntimeEventKind,
    new_id,
)


_PERSISTENT_RE = re.compile(
    r"\b(monitor|watch|track|keep an eye|alert me|notify me|whenever)\b",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "to", "and", "or", "for", "of", "my", "please",
    "that", "this", "with", "on", "in", "at", "is", "be", "it",
}


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def load_json(path: Path) -> Optional[Any]:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


class ObjectiveStore:
    """Durable store for Objectives. Not a chat log."""

    def __init__(self, storage_dir: Optional[str | Path] = None):
        if storage_dir is None:
            self._dir = get_storage_dir("objectives")
        else:
            self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, objective_id: str) -> Path:
        return self._dir / f"{objective_id}.json"

    def save(self, objective: Objective) -> Path:
        objective.touch()
        path = self._path(objective.objective_id)
        atomic_write_json(path, objective.to_dict())
        return path

    def get(self, objective_id: str) -> Optional[Objective]:
        data = load_json(self._path(objective_id))
        if not data:
            return None
        try:
            return Objective.from_dict(data)
        except (KeyError, TypeError, ValueError):
            return None

    def list_all(self) -> list[Objective]:
        items: list[Objective] = []
        for path in sorted(self._dir.glob("OBJ-*.json")):
            data = load_json(path)
            if not data:
                continue
            try:
                items.append(Objective.from_dict(data))
            except (KeyError, TypeError, ValueError):
                continue
        items.sort(key=lambda o: o.updated_at or o.created_at, reverse=True)
        return items

    def list_open(self) -> list[Objective]:
        return [o for o in self.list_all() if o.status in OPEN_OBJECTIVE_STATES]

    def list_by_status(self, status: ObjectiveState | str) -> list[Objective]:
        value = status.value if isinstance(status, ObjectiveState) else status
        return [o for o in self.list_all() if o.status == value]

    def match(self, text: str) -> Optional[Objective]:
        tokens = set(_TOKEN_RE.findall((text or "").lower())) - _STOP
        if not tokens:
            return None
        best: Optional[Objective] = None
        best_score = 0
        for obj in self.list_open():
            ot = set(_TOKEN_RE.findall(obj.intent.lower())) - _STOP
            score = len(tokens & ot)
            if score >= 2 and score > best_score:
                best = obj
                best_score = score
        return best

    def resolve(
        self,
        event: RuntimeEvent,
        *,
        active_objective_id: str = "",
    ) -> tuple[Objective, GoalIntent]:
        """Bind an event to an existing Objective or create one. UNDERSTAND stage."""
        if event.kind == RuntimeEventKind.APPROVAL.value and event.objective_id:
            existing = self.get(event.objective_id)
            if existing:
                return existing, classify_goal(existing.intent)

        if event.objective_id:
            existing = self.get(event.objective_id)
            if existing and existing.is_open:
                return existing, classify_goal(existing.intent)

        if active_objective_id and event.kind in {
            RuntimeEventKind.EXTERNAL_RESULT.value,
            RuntimeEventKind.SCHEDULED.value,
            RuntimeEventKind.TASK_COMPLETED.value,
            RuntimeEventKind.INTEGRATION.value,
        }:
            existing = self.get(active_objective_id)
            if existing and existing.is_open:
                return existing, classify_goal(existing.intent)

        text = event.text().strip()
        intent = classify_goal(text)
        matched = self.match(text)
        if matched is not None:
            return matched, intent

        kind = ObjectiveKind.PERSISTENT.value if _PERSISTENT_RE.search(text) else ObjectiveKind.ONE_SHOT.value
        if intent.kind == "remember":
            criteria = ["memory item exists"]
        elif intent.kind == "forget":
            criteria = ["matching memory removed"]
        elif kind == ObjectiveKind.PERSISTENT.value:
            criteria = ["continue observing relevant events"]
        else:
            criteria = ["verified action result"]

        objective = Objective(
            objective_id=new_id("OBJ"),
            intent=text,
            desired_outcome=text,
            status=ObjectiveState.PENDING.value,
            kind=kind,
            success_criteria=criteria,
        )
        return objective, intent
