# core/planner/schema.py
"""Planner v0.2 schema — structured plans with stable JSON.

A Plan is what the LLM produces.
A Task is what the runner executes.
Plans must be validated, then converted to Tasks.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


class PlanComplexity(str, Enum):
    """Estimated complexity of a plan."""
    TRIVIAL = "trivial"
    SIMPLE  = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


@dataclass
class VerificationCriterion:
    """A single verification check the planner thinks SHOULD be run.

    NOTE: Planner only defines what should be verified.
    Verification is performed later by the existing TaskRunner layer.
    """
    description: str
    # e.g. "typecheck passes", "no unrelated files modified"
    method: str = "manual"   # "manual" | "typecheck" | "test" | "diff" | "inspect"
    # Optional: command to run as part of verification
    command: str = ""
    args: list[str] = field(default_factory=list)
    expect_exit_code: int = 0
    verify_contains: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "VerificationCriterion":
        return cls(**d)


@dataclass
class PlanStep:
    """A single step in a plan.

    Conceptually maps 1:1 to core.tasks.schema.TaskStep, but is
    independent so the planner doesn't have to know runner internals.
    """
    step_id: str            # human-friendly: "step-1", "step-2"
    title: str
    description: str = ""
    step_type: str = "shell"  # "shell" | "python" | "inspect"
    dependencies: list[str] = field(default_factory=list)
    command: str = ""
    arguments: list[str] = field(default_factory=list)
    expected_result: str = ""
    # Optional verification hints per-step
    verify_contains: list[str] = field(default_factory=list)
    verify_not_contains: list[str] = field(default_factory=list)
    expect_exit_code: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PlanStep":
        return cls(**d)


@dataclass
class Plan:
    """A structured plan for a project task.

    The LLM returns this JSON shape. The validator checks it. Then the
    converter transforms it into a Task.
    """
    objective: str
    project_id: str
    steps: list[PlanStep]
    assumptions: list[str] = field(default_factory=list)
    verification: list[VerificationCriterion] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    estimated_complexity: PlanComplexity = PlanComplexity.SIMPLE
    # Free-form notes from the planner
    notes: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["steps"] = [s.to_dict() for s in self.steps]
        d["verification"] = [v.to_dict() for v in self.verification]
        d["estimated_complexity"] = self.estimated_complexity.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Plan":
        d = dict(d)
        d["steps"] = [PlanStep.from_dict(s) for s in d.get("steps", [])]
        d["verification"] = [
            VerificationCriterion.from_dict(v)
            for v in d.get("verification", [])
        ]
        c = d.get("estimated_complexity", "simple")
        d["estimated_complexity"] = PlanComplexity(c)
        return cls(**d)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> "Plan":
        return cls.from_dict(json.loads(text))

    def summary(self) -> str:
        return (
            f"Plan[{self.project_id}] {self.objective!r} — "
            f"{len(self.steps)} steps, "
            f"complexity={self.estimated_complexity.value}"
        )


# ── Validation ─────────────────────────────────────────────────────────

@dataclass
class ValidationError:
    """A single validation error."""
    code: str            # short code e.g. "EMPTY_OBJECTIVE"
    message: str         # human description
    field: str = ""      # dotted path to field, if any


@dataclass
class ValidationResult:
    """Result of validating a Plan."""
    valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "errors": [e.__dict__ for e in self.errors],
            "warnings": [w.__dict__ for w in self.warnings],
        }

    def add_error(self, code: str, message: str, field: str = "") -> None:
        self.errors.append(ValidationError(code, message, field))
        self.valid = False

    def add_warning(self, code: str, message: str, field: str = "") -> None:
        self.warnings.append(ValidationError(code, message, field))


# ── Step ID helpers ────────────────────────────────────────────────────

_STEP_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")


def is_valid_step_id(step_id: str) -> bool:
    return bool(_STEP_ID_RE.match(step_id))
