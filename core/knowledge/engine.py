# core/knowledge/engine.py
"""KnowledgeEngine — high-level orchestrator for the knowledge subsystem.

Combines: store, validator, lifecycle, relations, retrieval, promotion, provenance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core.knowledge.schema import (
    Primitive, KnowledgeStatus, SourceType, generate_primitive_id,
)
from core.knowledge.store import PrimitiveStore, StoreError
from core.knowledge.validator import KnowledgeValidator, ValidationReport
from core.knowledge.lifecycle import Lifecycle, LifecycleError
from core.knowledge.relations import RelationGraph, RelationError, Relation
from core.knowledge.index import InvertedIndex
from core.knowledge.retrieval import RetrievalEngine, RetrievalResult
from core.knowledge.ranking import Score
from core.knowledge.promotion import PromotionEngine, PromotionRecord
from core.knowledge.provenance import ProvenanceTracker, Evidence


@dataclass
class KnowledgeEngineStats:
    total: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    by_domain: dict[str, int] = field(default_factory=dict)


class KnowledgeEngine:
    """Public API for the knowledge subsystem.

    Usage:
        engine = KnowledgeEngine(store_dir="/path/to/knowledge")
        prim = engine.create_primitive(domain="...", concept="...", ...)
        engine.activate(prim, evidence_ids=[...])
        result = engine.retrieve("query", domain="...")
    """

    def __init__(self, store_dir: Optional[str] = None):
        self.store = PrimitiveStore(store_dir)
        self.validator = KnowledgeValidator()
        self.lifecycle = Lifecycle()
        self.relations = RelationGraph()
        self.promotion = PromotionEngine()
        self.provenance = ProvenanceTracker()

        # Load existing primitives
        prims = self.store.list_all()
        self.relations.load_from_store(prims)
        self._index = InvertedIndex(
            index_path=str(self.store._dir / "term_index.json")
        )
        self._index.rebuild_from_primitives(prims)
        self._index.save()
        self._retrieval = RetrievalEngine(prims, index=self._index, graph=self.relations)

    # ── Create / Update ─────────────────────────────────────────────

    def create_primitive(self, *, domain: str, concept: str,
                          description: str,
                          when_to_use: str = "",
                          implementation_pattern: str = "",
                          examples: Optional[list[str]] = None,
                          prerequisites: Optional[list[str]] = None,
                          failure_modes: Optional[list[str]] = None,
                          verification_method: str = "",
                          source_type: str = SourceType.MANUAL.value,
                          source_id: str = "",
                          created_by: str = "agent-core",
                          notes: str = "",
                          run_id: str = "") -> Primitive:
        """Create a new primitive (CANDIDATE by default)."""
        prim = Primitive(
            id=generate_primitive_id(),
            domain=domain,
            concept=concept,
            description=description,
            when_to_use=when_to_use,
            implementation_pattern=implementation_pattern,
            examples=list(examples or []),
            prerequisites=list(prerequisites or []),
            failure_modes=list(failure_modes or []),
            verification_method=verification_method,
            provenance=__import__("core.knowledge.schema", fromlist=["Provenance"]).Provenance(
                source_type=source_type,
                source_id=source_id,
                run_id=run_id,
                created_by=created_by,
                notes=notes,
            ),
            status=KnowledgeStatus.CANDIDATE.value,
        )
        # Validate before storing
        report = self.validator.validate(prim)
        if not report.valid:
            raise StoreError(f"Validation failed: {[e.message for e in report.errors]}")

        prim = self.store.create(prim)
        self.relations.add_primitive(prim)
        self._index.add(prim)
        self._index.save()
        self._retrieval.update(prim)
        return prim

    def update_primitive(self, prim: Primitive) -> Primitive:
        report = self.validator.validate(prim)
        if not report.valid:
            raise StoreError(f"Validation failed: {[e.message for e in report.errors]}")
        prim = self.store.update(prim)
        self.relations.add_primitive(prim)
        self._index.add(prim)
        self._index.save()
        self._retrieval.update(prim)
        return prim

    def get_primitive(self, prim_id: str) -> Optional[Primitive]:
        return self.store.get(prim_id)

    def delete_primitive(self, prim_id: str) -> bool:
        return self.store.delete(prim_id)

    def list_primitives(self) -> list[Primitive]:
        return self.store.list_all()

    def validate(self, prim: Primitive) -> ValidationReport:
        return self.validator.validate(prim)

    # ── Promotion ───────────────────────────────────────────────────

    def validate_primitive(self, prim: Primitive,
                            reason: str = "Validation",
                            promoted_by: str = "agent-core") -> tuple[Primitive, Optional[PromotionRecord]]:
        return self.promotion.promote(prim, KnowledgeStatus.VALIDATED.value,
                                       reason=reason, promoted_by=promoted_by)

    def verify_primitive(self, prim: Primitive,
                          evidence_id: str,
                          reason: str = "Verification") -> tuple[Primitive, Optional[PromotionRecord]]:
        return self.promotion.promote(prim, KnowledgeStatus.VERIFIED.value,
                                       reason=reason, evidence_ids=[evidence_id])

    def activate_primitive(self, prim: Primitive,
                            evidence_ids: list[str],
                            reason: str = "Activation") -> tuple[Primitive, Optional[PromotionRecord]]:
        return self.promotion.promote(prim, KnowledgeStatus.ACTIVE.value,
                                       reason=reason, evidence_ids=evidence_ids)

    def deprecate_primitive(self, prim: Primitive, reason: str = "Deprecated") -> Primitive:
        prim = self.promotion.promote(prim, KnowledgeStatus.DEPRECATED.value,
                                       reason=reason)
        return prim[0]

    # ── Relations ───────────────────────────────────────────────────

    def add_relation(self, source_id: str, target_id: str,
                      relation_type: str, weight: float = 1.0,
                      note: str = "") -> None:
        self.relations.add_relation(source_id, Relation(
            target_id=target_id,
            relation_type=relation_type,
            weight=weight,
            note=note,
        ))
        # Persist update
        src = self.relations.primitives.get(source_id)
        if src:
            self.store.update(src)

    def get_related(self, prim_id: str,
                    relation_type: Optional[str] = None,
                    max_depth: int = 1) -> list[str]:
        return self.relations.get_related(prim_id, relation_type, max_depth)

    # ── Retrieval ──────────────────────────────────────────────────

    def retrieve(self, query: str, domain: Optional[str] = None,
                 top_k: int = 5, expand_depth: int = 0) -> RetrievalResult:
        return self._retrieval.retrieve(query, domain=domain, top_k=top_k, expand_depth=expand_depth)

    def record_evidence(self, evidence: Evidence) -> Evidence:
        return self.provenance.record(evidence)

    # ── Analytics ───────────────────────────────────────────────────

    def stats(self) -> KnowledgeEngineStats:
        prims = self.list_primitives()
        s = KnowledgeEngineStats(total=len(prims))
        for p in prims:
            s.by_status[p.status] = s.by_status.get(p.status, 0) + 1
            s.by_domain[p.domain] = s.by_domain.get(p.domain, 0) + 1
        return s
