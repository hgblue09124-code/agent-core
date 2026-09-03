# core/knowledge/schema.py
"""Primitive Knowledge Engine v0.7 — schemas & lifecycle.

A Primitive is a deterministic, evidence-backed knowledge unit the kernel
can retrieve, validate, and promote through a strict lifecycle.

Design:
    - No LLM in this module. Pure data.
    - All state mutations go through the lifecycle state machine.
    - Provenance is mandatory: every primitive records how it was born.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


# ── Lifecycle states ─────────────────────────────────────────────────────

class KnowledgeStatus(str, Enum):
    """Explicit state machine for primitives.

    Only the following transitions are legal:
        CANDIDATE   -> VALIDATED, REJECTED
        VALIDATED   -> VERIFIED, DEPRECATED
        VERIFIED    -> ACTIVE, DEPRECATED
        ACTIVE      -> DEPRECATED
    Anything else is rejected by `lifecycle.can_transition()`.
    """
    CANDIDATE = "CANDIDATE"
    VALIDATED = "VALIDATED"
    VERIFIED  = "VERIFIED"
    ACTIVE    = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    REJECTED  = "REJECTED"


# ── Provenance ──────────────────────────────────────────────────────────

class SourceType(str, Enum):
    MANUAL    = "manual"      # human-written
    OBSERVED  = "observed"    # recorded from real execution
    GENERATED = "generated"   # created by code/LLM without verification
    VERIFIED  = "verified"    # promoted from observation after evidence
    DERIVED   = "derived"     # constructed from other primitives


@dataclass
class Provenance:
    """How a primitive was created.

    `created_by` should be a system name (e.g. "agent-core-kernel"),
    never a personal identifier.
    """
    source_type: str = SourceType.GENERATED.value
    source_id: str = ""
    run_id: str = ""
    evidence_ids: list[str] = field(default_factory=list)
    created_by: str = "agent-core"
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "source_type": self.source_type,
            "source_id": self.source_id,
            "run_id": self.run_id,
            "evidence_ids": list(self.evidence_ids),
            "created_by": self.created_by,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Provenance":
        return cls(
            source_type=d.get("source_type", SourceType.GENERATED.value),
            source_id=d.get("source_id", ""),
            run_id=d.get("run_id", ""),
            evidence_ids=list(d.get("evidence_ids", [])),
            created_by=d.get("created_by", "agent-core"),
            notes=d.get("notes", ""),
        )


# ── Relations ───────────────────────────────────────────────────────────

class RelationType(str, Enum):
    REQUIRES            = "REQUIRES"
    ALTERNATIVE_TO      = "ALTERNATIVE_TO"
    IMPROVES            = "IMPROVES"
    DEPENDS_ON          = "DEPENDS_ON"
    CONFLICTS_WITH      = "CONFLICTS_WITH"
    COMMONLY_FAILS_WITH = "COMMONLY_FAILS_WITH"
    DERIVED_FROM        = "DERIVED_FROM"
    SUPERSEDES          = "SUPERSEDES"


# Relations that may NOT be self-loops (most can't)
_NO_SELF_LOOP = {rt for rt in RelationType}
# Relations that are antisymmetric (A→B implies not B→A)
_ANTISYMMETRIC = {
    RelationType.REQUIRES,
    RelationType.DEPENDS_ON,
    RelationType.IMPROVES,
    RelationType.DERIVED_FROM,
    RelationType.SUPERSEDES,
}


@dataclass
class Relation:
    """Typed edge in the knowledge graph.

    `target_id` references another primitive. `weight` is used for ranking.
    """
    target_id: str
    relation_type: str
    weight: float = 1.0
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "weight": self.weight,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Relation":
        return cls(
            target_id=d["target_id"],
            relation_type=d["relation_type"],
            weight=float(d.get("weight", 1.0)),
            note=d.get("note", ""),
        )


# ── Primitive ───────────────────────────────────────────────────────────

_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{3,64}$")


@dataclass
class Primitive:
    """A single knowledge primitive.

    The schema is deliberately explicit. Loose dicts are NOT a public model.
    """
    # Identity
    id: str
    domain: str
    concept: str
    description: str

    # Pattern fields
    when_to_use: str = ""
    implementation_pattern: str = ""
    examples: list[str] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)
    failure_modes: list[str] = field(default_factory=list)
    verification_method: str = ""

    # Graph
    related_primitives: list[str] = field(default_factory=list)  # legacy, kept for compat
    relations: list[Relation] = field(default_factory=list)

    # Lineage
    provenance: Provenance = field(default_factory=Provenance)
    confidence: float = 0.0          # 0.0 .. 1.0; never set to 1.0 without ACTIVE
    version: int = 1

    # Lifecycle
    status: str = KnowledgeStatus.CANDIDATE.value
    created_at: str = ""
    updated_at: str = ""

    # Usage telemetry
    usage_count: int = 0
    success_count: int = 0
    failure_count: int = 0

    # Schema version (for migration)
    schema_version: int = 1

    # ── Serialisation ────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "domain": self.domain,
            "concept": self.concept,
            "description": self.description,
            "when_to_use": self.when_to_use,
            "implementation_pattern": self.implementation_pattern,
            "examples": list(self.examples),
            "prerequisites": list(self.prerequisites),
            "failure_modes": list(self.failure_modes),
            "verification_method": self.verification_method,
            "related_primitives": list(self.related_primitives),
            "relations": [r.to_dict() for r in self.relations],
            "provenance": self.provenance.to_dict(),
            "confidence": self.confidence,
            "version": self.version,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "usage_count": self.usage_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Primitive":
        return cls(
            id=d["id"],
            domain=d.get("domain", "general"),
            concept=d.get("concept", ""),
            description=d.get("description", ""),
            when_to_use=d.get("when_to_use", ""),
            implementation_pattern=d.get("implementation_pattern", ""),
            examples=list(d.get("examples", [])),
            prerequisites=list(d.get("prerequisites", [])),
            failure_modes=list(d.get("failure_modes", [])),
            verification_method=d.get("verification_method", ""),
            related_primitives=list(d.get("related_primitives", [])),
            relations=[Relation.from_dict(r) for r in d.get("relations", [])],
            provenance=Provenance.from_dict(d.get("provenance", {})),
            confidence=float(d.get("confidence", 0.0)),
            version=int(d.get("version", 1)),
            status=d.get("status", KnowledgeStatus.CANDIDATE.value),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            usage_count=int(d.get("usage_count", 0)),
            success_count=int(d.get("success_count", 0)),
            failure_count=int(d.get("failure_count", 0)),
            schema_version=int(d.get("schema_version", 1)),
        )

    # ── Helpers ──────────────────────────────────────────────────────

    def success_rate(self) -> float:
        if self.usage_count == 0:
            return 0.0
        return self.success_count / self.usage_count

    def is_usable(self) -> bool:
        """A primitive is only usable at ACTIVE."""
        return self.status == KnowledgeStatus.ACTIVE.value

    def now_str(self) -> str:
        return datetime.now(timezone.utc).isoformat()


# ── ID generation ───────────────────────────────────────────────────────

def generate_primitive_id(prefix: str = "PRIM") -> str:
    """Deterministic-safe id using monotonic time.

    Format: PREFIX-NNNNN (zero-padded)
    """
    return f"{prefix}-{int(time.time() * 1000) % 100000:05d}"
