# core/knowledge/__init__.py
"""Knowledge Engine v0.7 — primitive knowledge with lifecycle, relations, retrieval."""

from core.knowledge.schema import (
    Primitive, Provenance, Relation, RelationType,
    KnowledgeStatus, SourceType, generate_primitive_id,
)
from core.knowledge.store import PrimitiveStore, StoreError
from core.knowledge.lifecycle import Lifecycle, LifecycleError
from core.knowledge.validator import KnowledgeValidator, ValidationReport
from core.knowledge.relations import RelationGraph, RelationError
from core.knowledge.index import InvertedIndex
from core.knowledge.ranking import Ranker, Score
from core.knowledge.retrieval import RetrievalEngine, RetrievalResult
from core.knowledge.promotion import PromotionEngine, PromotionRecord
from core.knowledge.provenance import ProvenanceTracker, Evidence
from core.knowledge.engine import KnowledgeEngine, KnowledgeEngineStats

__all__ = [
    "Primitive", "Provenance", "Relation", "RelationType",
    "KnowledgeStatus", "SourceType", "generate_primitive_id",
    "PrimitiveStore", "StoreError",
    "Lifecycle", "LifecycleError",
    "KnowledgeValidator", "ValidationReport",
    "RelationGraph", "RelationError",
    "InvertedIndex",
    "Ranker", "Score",
    "RetrievalEngine", "RetrievalResult",
    "PromotionEngine", "PromotionRecord",
    "ProvenanceTracker", "Evidence",
    "KnowledgeEngine", "KnowledgeEngineStats",
]
