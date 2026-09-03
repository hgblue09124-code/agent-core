# core/knowledge/validator.py
"""Schema & semantic validation for primitives.

Validation layers:
    1. Schema validation      — all required fields present and well-typed
    2. Semantic validation    — non-empty key fields, valid IDs
    3. Provenance validation  — source_type recognised, no secrets
    4. Lifecycle validation   — status is recognised
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from core.knowledge.schema import Primitive, SourceType, KnowledgeStatus


_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"xoxb-[A-Za-z0-9-]{20,}"),
]


@dataclass
class ValidationIssue:
    code: str
    field: str
    message: str


@dataclass
class ValidationReport:
    valid: bool
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)

    def add_error(self, code: str, field: str, message: str) -> None:
        self.errors.append(ValidationIssue(code=code, field=field, message=message))
        self.valid = False

    def add_warning(self, code: str, field: str, message: str) -> None:
        self.warnings.append(ValidationIssue(code=code, field=field, message=message))


_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{3,64}$")


class KnowledgeValidator:
    """Validates primitives. Pure function — no I/O."""

    def validate(self, prim: Primitive) -> ValidationReport:
        report = ValidationReport(valid=True)
        self._validate_schema(prim, report)
        self._validate_semantic(prim, report)
        self._validate_provenance(prim, report)
        self._validate_lifecycle(prim, report)
        return report

    # ── Layer 1: schema ──────────────────────────────────────────────

    def _validate_schema(self, prim: Primitive, r: ValidationReport) -> None:
        if not prim.id:
            r.add_error("SCHEMA_MISSING_ID", "id", "id is required")
        elif not _ID_RE.match(prim.id):
            r.add_error("SCHEMA_BAD_ID", "id", f"id has bad format: {prim.id!r}")
        if not prim.domain:
            r.add_error("SCHEMA_MISSING_DOMAIN", "domain", "domain is required")
        if not prim.concept:
            r.add_error("SCHEMA_MISSING_CONCEPT", "concept", "concept is required")
        if not prim.description:
            r.add_error("SCHEMA_MISSING_DESCRIPTION", "description", "description is required")
        if not (0.0 <= prim.confidence <= 1.0):
            r.add_error("SCHEMA_BAD_CONFIDENCE", "confidence",
                        f"confidence must be in [0,1], got {prim.confidence}")
        if prim.usage_count < 0 or prim.success_count < 0 or prim.failure_count < 0:
            r.add_error("SCHEMA_NEGATIVE_COUNT", "usage",
                        "counts must be non-negative")
        if prim.success_count + prim.failure_count > prim.usage_count:
            r.add_error("SCHEMA_COUNT_INCONSISTENT", "usage",
                        "success+failure > usage")

    # ── Layer 2: semantic ───────────────────────────────────────────

    def _validate_semantic(self, prim: Primitive, r: ValidationReport) -> None:
        if not prim.when_to_use:
            r.add_warning("SEMANTIC_NO_WHEN", "when_to_use",
                          "when_to_use is empty — primitive is less retrievable")
        if not prim.implementation_pattern:
            r.add_warning("SEMANTIC_NO_PATTERN", "implementation_pattern",
                          "no implementation pattern — harder to reuse")
        if not prim.verification_method:
            r.add_warning("SEMANTIC_NO_VERIFICATION", "verification_method",
                          "no verification method — promotion will be hard")

    # ── Layer 3: provenance ──────────────────────────────────────────

    def _validate_provenance(self, prim: Primitive, r: ValidationReport) -> None:
        prov = prim.provenance
        valid_types = {t.value for t in SourceType}
        if prov.source_type not in valid_types:
            r.add_error("PROVENANCE_BAD_TYPE", "provenance.source_type",
                        f"source_type {prov.source_type!r} not in {valid_types}")
        if not prov.created_by:
            r.add_error("PROVENANCE_MISSING_AUTHOR", "provenance.created_by",
                        "created_by is required")

        # Hard rule: no secrets in provenance
        all_text = " ".join([
            prov.source_id, prov.run_id, prov.created_by, prov.notes,
        ])
        for pat in _SECRET_PATTERNS:
            if pat.search(all_text):
                r.add_error("PROVENANCE_SECRET_DETECTED", "provenance",
                            "provenance field looks like a secret")
                return

    # ── Layer 4: lifecycle ───────────────────────────────────────────

    def _validate_lifecycle(self, prim: Primitive, r: ValidationReport) -> None:
        valid = {s.value for s in KnowledgeStatus}
        if prim.status not in valid:
            r.add_error("LIFECYCLE_BAD_STATUS", "status",
                        f"status {prim.status!r} not in {valid}")

        # Generated primitives must NOT be ACTIVE
        if prim.provenance.source_type == SourceType.GENERATED.value and prim.status == KnowledgeStatus.ACTIVE.value:
            r.add_error("LIFECYCLE_GENERATED_ACTIVE", "status",
                        "Generated primitives cannot be ACTIVE without verification")

        # Confidence guard: ACTIVE requires confidence >= 0.5
        if prim.status == KnowledgeStatus.ACTIVE.value and prim.confidence < 0.5:
            r.add_error("LIFECYCLE_ACTIVE_LOW_CONFIDENCE", "confidence",
                        f"ACTIVE primitive requires confidence >= 0.5, got {prim.confidence}")


def validate_primitives(prims: Iterable[Primitive]) -> dict[str, ValidationReport]:
    """Validate many primitives. Returns id -> report."""
    v = KnowledgeValidator()
    return {p.id: v.validate(p) for p in prims}
