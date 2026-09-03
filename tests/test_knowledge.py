#!/usr/bin/env python3
# tests/test_knowledge.py
"""Knowledge Engine v0.7 tests — schema, lifecycle, persistence, retrieval, etc."""

import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def _make_prim(**kw):
    from core.knowledge.schema import Primitive, KnowledgeStatus, SourceType
    from datetime import datetime, timezone
    defaults = dict(
        id="PRIM-00001",
        domain="test",
        concept="atomic write",
        description="write file via tmp + fsync + rename",
        when_to_use="when persisting critical state",
        implementation_pattern="open(tmp) → flush → os.fsync → os.replace",
        examples=["checkpoint files"],
        prerequisites=["python stdlib"],
        failure_modes=["power loss mid-write"],
        verification_method="read after write returns valid JSON",
        status=KnowledgeStatus.CANDIDATE.value,
        confidence=0.0,
    )
    defaults.update(kw)
    return Primitive(**defaults)


# ── Schema & serialisation ──────────────────────────────────────────────

class TestSchema(unittest.TestCase):

    def test_primitive_to_dict_roundtrip(self):
        p = _make_prim()
        d = p.to_dict()
        p2 = type(p).from_dict(d)
        self.assertEqual(p.id, p2.id)
        self.assertEqual(p.domain, p2.domain)
        self.assertEqual(p.concept, p2.concept)
        self.assertEqual(p.relations, p2.relations)

    def test_provenance_roundtrip(self):
        from core.knowledge.schema import Provenance
        p = Provenance(source_type="manual", source_id="x", run_id="R1",
                        evidence_ids=["e1", "e2"], created_by="cli")
        d = p.to_dict()
        p2 = Provenance.from_dict(d)
        self.assertEqual(p.source_id, p2.source_id)
        self.assertEqual(p.evidence_ids, p2.evidence_ids)

    def test_relation_roundtrip(self):
        from core.knowledge.schema import Relation
        r = Relation(target_id="X", relation_type="REQUIRES", weight=0.8)
        d = r.to_dict()
        r2 = Relation.from_dict(d)
        self.assertEqual(r.target_id, r2.target_id)
        self.assertEqual(r.relation_type, r2.relation_type)
        self.assertEqual(r.weight, r2.weight)


# ── Lifecycle ───────────────────────────────────────────────────────────

class TestLifecycle(unittest.TestCase):

    def test_candidate_to_validated(self):
        from core.knowledge.lifecycle import Lifecycle
        lc = Lifecycle()
        self.assertTrue(lc.can_transition("CANDIDATE", "VALIDATED"))

    def test_candidate_to_active_illegal(self):
        from core.knowledge.lifecycle import Lifecycle
        lc = Lifecycle()
        # ACTIVE requires going through VALIDATED -> VERIFIED
        self.assertFalse(lc.can_transition("CANDIDATE", "ACTIVE"))

    def test_full_happy_path(self):
        from core.knowledge.lifecycle import Lifecycle
        lc = Lifecycle()
        for src, dst in [
            ("CANDIDATE", "VALIDATED"),
            ("VALIDATED", "VERIFIED"),
            ("VERIFIED", "ACTIVE"),
            ("ACTIVE", "DEPRECATED"),
        ]:
            self.assertTrue(lc.can_transition(src, dst),
                            f"{src} → {dst} should be legal")

    def test_apply_rejects_illegal(self):
        from core.knowledge.lifecycle import Lifecycle, LifecycleError
        lc = Lifecycle()
        with self.assertRaises(LifecycleError):
            lc.apply("CANDIDATE", "ACTIVE")

    def test_deprecated_is_terminal(self):
        from core.knowledge.lifecycle import Lifecycle
        lc = Lifecycle()
        for target in ("CANDIDATE", "VALIDATED", "VERIFIED", "ACTIVE"):
            self.assertFalse(lc.can_transition("DEPRECATED", target))

    def test_rejected_is_terminal(self):
        from core.knowledge.lifecycle import Lifecycle
        lc = Lifecycle()
        for target in ("CANDIDATE", "VALIDATED", "VERIFIED", "ACTIVE"):
            self.assertFalse(lc.can_transition("REJECTED", target))


# ── Validator ──────────────────────────────────────────────────────────

class TestValidator(unittest.TestCase):

    def test_valid_primitive(self):
        from core.knowledge.validator import KnowledgeValidator
        v = KnowledgeValidator()
        r = v.validate(_make_prim())
        self.assertTrue(r.valid, f"errors: {[e.message for e in r.errors]}")

    def test_missing_concept(self):
        from core.knowledge.validator import KnowledgeValidator
        v = KnowledgeValidator()
        p = _make_prim(concept="")
        r = v.validate(p)
        self.assertFalse(r.valid)
        self.assertTrue(any(e.code == "SCHEMA_MISSING_CONCEPT" for e in r.errors))

    def test_bad_confidence(self):
        from core.knowledge.validator import KnowledgeValidator
        v = KnowledgeValidator()
        p = _make_prim(confidence=1.5)
        r = v.validate(p)
        self.assertFalse(r.valid)

    def test_generated_cannot_be_active(self):
        from core.knowledge.validator import KnowledgeValidator
        from core.knowledge.schema import SourceType, KnowledgeStatus
        v = KnowledgeValidator()
        p = _make_prim()
        p.provenance.source_type = SourceType.GENERATED.value
        p.status = KnowledgeStatus.ACTIVE.value
        r = v.validate(p)
        self.assertFalse(r.valid)
        self.assertTrue(any(e.code == "LIFECYCLE_GENERATED_ACTIVE" for e in r.errors))

    def test_active_low_confidence_rejected(self):
        from core.knowledge.validator import KnowledgeValidator
        from core.knowledge.schema import SourceType, KnowledgeStatus
        v = KnowledgeValidator()
        p = _make_prim(confidence=0.1)
        p.provenance.source_type = SourceType.MANUAL.value
        p.status = KnowledgeStatus.ACTIVE.value
        r = v.validate(p)
        self.assertFalse(r.valid)

    def test_secret_in_provenance_rejected(self):
        from core.knowledge.validator import KnowledgeValidator
        from core.knowledge.schema import SourceType
        v = KnowledgeValidator()
        p = _make_prim()
        p.provenance.notes = "sk-abcdefghijklmnopqrstuvwxyz12345"
        r = v.validate(p)
        self.assertFalse(r.valid)


# ── Store / persistence ────────────────────────────────────────────────

class TestStore(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))

    def test_create_and_get(self):
        from core.knowledge.store import PrimitiveStore
        s = PrimitiveStore(self.tmpdir)
        p = _make_prim(id="PRIM-T1")
        s.create(p)
        loaded = s.get("PRIM-T1")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.id, "PRIM-T1")
        self.assertEqual(loaded.concept, p.concept)

    def test_atomic_write_no_tmp(self):
        from core.knowledge.store import PrimitiveStore
        s = PrimitiveStore(self.tmpdir)
        s.create(_make_prim(id="PRIM-AT1"))
        # .tmp file should not remain
        self.assertFalse((Path(self.tmpdir) / "PRIM-AT1.json.tmp").exists())
        # main file exists
        self.assertTrue((Path(self.tmpdir) / "PRIM-AT1.json").exists())

    def test_duplicate_rejected(self):
        from core.knowledge.store import PrimitiveStore, StoreError
        s = PrimitiveStore(self.tmpdir)
        s.create(_make_prim(id="PRIM-DUP"))
        with self.assertRaises(StoreError):
            s.create(_make_prim(id="PRIM-DUP"))

    def test_update_increments_version(self):
        from core.knowledge.store import PrimitiveStore
        s = PrimitiveStore(self.tmpdir)
        p = _make_prim(id="PRIM-UP")
        s.create(p)
        p.description = "Updated"
        s.update(p)
        self.assertEqual(p.version, 2)
        loaded = s.get("PRIM-UP")
        self.assertEqual(loaded.description, "Updated")

    def test_corrupt_file_returns_none(self):
        from core.knowledge.store import PrimitiveStore
        s = PrimitiveStore(self.tmpdir)
        # Write a broken file
        (Path(self.tmpdir) / "PRIM-BAD.json").write_text("{ bad")
        self.assertIsNone(s.get("PRIM-BAD"))

    def test_list_all(self):
        from core.knowledge.store import PrimitiveStore
        s = PrimitiveStore(self.tmpdir)
        s.create(_make_prim(id="PRIM-L1"))
        s.create(_make_prim(id="PRIM-L2"))
        prims = s.list_all()
        self.assertEqual(len(prims), 2)


# ── Relations ─────────────────────────────────────────────────────────

class TestRelations(unittest.TestCase):

    def test_add_relation(self):
        from core.knowledge.relations import RelationGraph, Relation
        from core.knowledge.relations import RelationError
        from core.knowledge.schema import RelationType
        g = RelationGraph()
        g.add_primitive(_make_prim(id="A"))
        g.add_primitive(_make_prim(id="B"))
        g.add_relation("A", Relation(target_id="B",
                                       relation_type=RelationType.REQUIRES.value))
        self.assertEqual(len(g.primitives["A"].relations), 1)

    def test_self_loop_rejected(self):
        from core.knowledge.relations import RelationGraph, Relation, RelationError
        g = RelationGraph()
        g.add_primitive(_make_prim(id="A"))
        with self.assertRaises(RelationError):
            g.add_relation("A", Relation(target_id="A", relation_type="REQUIRES"))

    def test_duplicate_edge_rejected(self):
        from core.knowledge.relations import RelationGraph, Relation, RelationError
        g = RelationGraph()
        g.add_primitive(_make_prim(id="A"))
        g.add_primitive(_make_prim(id="B"))
        g.add_relation("A", Relation(target_id="B", relation_type="REQUIRES"))
        with self.assertRaises(RelationError):
            g.add_relation("A", Relation(target_id="B", relation_type="REQUIRES"))

    def test_antisymmetric_rejected(self):
        from core.knowledge.relations import RelationGraph, Relation, RelationError
        g = RelationGraph()
        g.add_primitive(_make_prim(id="A"))
        g.add_primitive(_make_prim(id="B"))
        g.add_relation("A", Relation(target_id="B", relation_type="REQUIRES"))
        with self.assertRaises(RelationError):
            g.add_relation("B", Relation(target_id="A", relation_type="REQUIRES"))

    def test_target_must_exist(self):
        from core.knowledge.relations import RelationGraph, Relation, RelationError
        g = RelationGraph()
        g.add_primitive(_make_prim(id="A"))
        with self.assertRaises(RelationError):
            g.add_relation("A", Relation(target_id="NOPE", relation_type="REQUIRES"))

    def test_bounded_expansion(self):
        from core.knowledge.relations import RelationGraph, Relation
        g = RelationGraph()
        g.add_primitive(_make_prim(id="A"))
        g.add_primitive(_make_prim(id="B"))
        g.add_primitive(_make_prim(id="C"))
        g.add_primitive(_make_prim(id="D"))
        # A -> B, B -> C, C -> D
        g.add_relation("A", Relation(target_id="B", relation_type="REQUIRES"))
        g.add_relation("B", Relation(target_id="C", relation_type="REQUIRES"))
        g.add_relation("C", Relation(target_id="D", relation_type="REQUIRES"))

        depth_1 = g.get_related("A", max_depth=1)
        self.assertIn("B", depth_1)
        self.assertNotIn("C", depth_1)

        depth_2 = g.get_related("A", max_depth=2)
        self.assertIn("B", depth_2)
        self.assertIn("C", depth_2)
        self.assertNotIn("D", depth_2)

    def test_find_cycles(self):
        from core.knowledge.relations import RelationGraph, Relation
        g = RelationGraph()
        g.add_primitive(_make_prim(id="A"))
        g.add_primitive(_make_prim(id="B"))
        # Bypass the antisymmetric validator for cycle test
        a_prim = g.primitives["A"]
        b_prim = g.primitives["B"]
        a_prim.relations.append(Relation(target_id="B", relation_type="REQUIRES"))
        b_prim.relations.append(Relation(target_id="A", relation_type="REQUIRES"))
        cycles = g.find_cycles()
        self.assertGreater(len(cycles), 0)


# ── Retrieval & ranking ───────────────────────────────────────────────

class TestRetrieval(unittest.TestCase):

    def test_keyword_match(self):
        from core.knowledge.engine import KnowledgeEngine
        import tempfile, shutil
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        engine = KnowledgeEngine(d)
        engine.create_primitive(
            domain="storage",
            concept="atomic write",
            description="file replace",
            when_to_use="persist state",
        )
        engine.create_primitive(
            domain="network",
            concept="http get",
            description="fetch data",
        )
        result = engine.retrieve("atomic file write", top_k=2)
        self.assertGreater(len(result.scores), 0)
        # Top hit should be the atomic write primitive (first created)
        top_prim = engine.get_primitive(result.scores[0].primitive_id)
        self.assertIn("atomic", top_prim.concept.lower())

    def test_domain_filter(self):
        from core.knowledge.engine import KnowledgeEngine
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        engine = KnowledgeEngine(d)
        engine.create_primitive(domain="storage", concept="checkpoint", description="x")
        engine.create_primitive(domain="network", concept="http", description="y")
        result = engine.retrieve("any", domain="storage", top_k=5)
        ids = [s.primitive_id for s in result.scores]
        for pid in ids:
            prim = engine.get_primitive(pid)
            self.assertEqual(prim.domain, "storage")

    def test_ranking_prefers_active_with_high_confidence(self):
        from core.knowledge.engine import KnowledgeEngine
        from core.knowledge.schema import KnowledgeStatus
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        engine = KnowledgeEngine(d)
        p1 = engine.create_primitive(domain="d", concept="checkpoint atomic",
                                       description="durable state")
        p2 = engine.create_primitive(domain="d", concept="other atomic",
                                       description="something else")
        # Promote p1 through full lifecycle
        p1, _ = engine.validate_primitive(p1)
        p1, _ = engine.verify_primitive(p1, evidence_id="ev-1")
        p1.confidence = 0.9
        engine.update_primitive(p1)
        # p1 has higher confidence, should rank higher
        result = engine.retrieve("checkpoint atomic", top_k=2)
        if len(result.scores) >= 2:
            top_id = result.scores[0].primitive_id
            self.assertEqual(top_id, p1.id)

    def test_empty_query(self):
        from core.knowledge.engine import KnowledgeEngine
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        engine = KnowledgeEngine(d)
        result = engine.retrieve("   ", top_k=5)
        self.assertEqual(len(result.scores), 0)


# ── Promotion ──────────────────────────────────────────────────────────

class TestPromotion(unittest.TestCase):

    def test_promote_candidate_to_validated(self):
        from core.knowledge.engine import KnowledgeEngine
        from core.knowledge.lifecycle import LifecycleError
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        engine = KnowledgeEngine(d)
        p = engine.create_primitive(domain="d", concept="x", description="y")
        p, _ = engine.validate_primitive(p)
        self.assertEqual(p.status, "VALIDATED")

    def test_cannot_skip_to_active(self):
        from core.knowledge.engine import KnowledgeEngine
        from core.knowledge.lifecycle import LifecycleError
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        engine = KnowledgeEngine(d)
        p = engine.create_primitive(domain="d", concept="x", description="y")
        with self.assertRaises(LifecycleError):
            engine.activate_primitive(p, evidence_ids=["e1"], reason="x")

    def test_activate_requires_evidence(self):
        from core.knowledge.engine import KnowledgeEngine
        from core.knowledge.lifecycle import LifecycleError
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        engine = KnowledgeEngine(d)
        p = engine.create_primitive(domain="d", concept="x", description="y")
        p, _ = engine.validate_primitive(p)
        p, _ = engine.verify_primitive(p, evidence_id="e1")
        with self.assertRaises(LifecycleError):
            # No evidence IDs
            engine.activate_primitive(p, evidence_ids=[], reason="x")

    def test_generated_cannot_activate(self):
        from core.knowledge.engine import KnowledgeEngine
        from core.knowledge.lifecycle import LifecycleError
        from core.knowledge.schema import SourceType
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        engine = KnowledgeEngine(d)
        p = engine.create_primitive(domain="d", concept="x", description="y",
                                       source_type=SourceType.GENERATED.value)
        p, _ = engine.validate_primitive(p)
        p, _ = engine.verify_primitive(p, evidence_id="e1")
        with self.assertRaises(LifecycleError):
            engine.activate_primitive(p, evidence_ids=["e1", "e2"], reason="x")

    def test_full_promotion_path(self):
        from core.knowledge.engine import KnowledgeEngine
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        engine = KnowledgeEngine(d)
        p = engine.create_primitive(domain="d", concept="x", description="y")
        p, _ = engine.validate_primitive(p)
        # Verify needs at least 1 evidence; activate needs total >= 2 unique
        p, _ = engine.verify_primitive(p, evidence_id="e1")
        p.confidence = 0.8
        # Add second evidence without changing status
        p = engine.promotion.record_observation(p, "second observation", "e2")
        engine.update_primitive(p)
        p, _ = engine.activate_primitive(p, evidence_ids=["e1", "e2"], reason="full path")
        self.assertEqual(p.status, "ACTIVE")


# ── Provenance ────────────────────────────────────────────────────────

class TestProvenance(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))

    def test_record_evidence(self):
        from core.knowledge.provenance import ProvenanceTracker, Evidence
        tracker = ProvenanceTracker(str(Path(self.tmpdir) / "evidence.json"))
        ev = Evidence(evidence_id="e1", type="test", source="unit test", result="PASS")
        tracker.record(ev)
        loaded = tracker.get("e1")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.type, "test")

    def test_secret_rejected(self):
        from core.knowledge.provenance import ProvenanceTracker, Evidence
        tracker = ProvenanceTracker(str(Path(self.tmpdir) / "evidence.json"))
        ev = Evidence(evidence_id="e1", type="manual",
                       source="leak", result="sk-abcdefghijklmnopqrstuvwxyz12345")
        with self.assertRaises(ValueError):
            tracker.record(ev)

    def test_find_by_run(self):
        from core.knowledge.provenance import ProvenanceTracker, Evidence
        tracker = ProvenanceTracker(str(Path(self.tmpdir) / "evidence.json"))
        tracker.record(Evidence(evidence_id="e1", type="test", source="x", result="y",
                                  run_id="RUN-1"))
        tracker.record(Evidence(evidence_id="e2", type="test", source="x", result="y",
                                  run_id="RUN-2"))
        found = tracker.find_by_run("RUN-1")
        self.assertEqual(len(found), 1)


# ── Index ──────────────────────────────────────────────────────────────

class TestIndex(unittest.TestCase):

    def test_inverted_index_rebuild(self):
        from core.knowledge.index import InvertedIndex
        idx = InvertedIndex()
        prims = [
            _make_prim(id="A", concept="checkpoint atomic", description="durable write"),
            _make_prim(id="B", concept="http fetch", description="network call"),
        ]
        idx.rebuild_from_primitives(prims)
        self.assertEqual(idx.count(), 2)
        results = idx.search("checkpoint")
        ids = [pid for pid, _ in results]
        self.assertIn("A", ids)
        self.assertNotIn("B", ids)

    def test_index_persistence(self):
        from core.knowledge.index import InvertedIndex
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        idx = InvertedIndex(index_path=str(Path(d) / "idx.json"))
        idx.rebuild_from_primitives([_make_prim(id="A", concept="x", description="y")])
        idx.save()
        idx2 = InvertedIndex(index_path=str(Path(d) / "idx.json"))
        ok = idx2.load()
        self.assertTrue(ok)
        self.assertEqual(idx2.count(), 1)


# ── Migration ─────────────────────────────────────────────────────────

class TestMigration(unittest.TestCase):

    def test_old_version_migrates(self):
        from core.knowledge.store import PrimitiveStore
        from core.knowledge.schema import Primitive
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        store = PrimitiveStore(d)
        # Write a primitive with old schema_version
        old = _make_prim(id="OLD-1")
        old.schema_version = 0
        import json
        (Path(d) / "OLD-1.json").write_text(json.dumps(old.to_dict()))
        loaded = store.get("OLD-1")
        self.assertIsNotNone(loaded)
        # Should be migrated to v1
        self.assertEqual(loaded.schema_version, 1)


# ── Adversarial ───────────────────────────────────────────────────────

class TestAdversarial(unittest.TestCase):

    def test_corrupt_file_handled(self):
        from core.knowledge.store import PrimitiveStore
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        store = PrimitiveStore(d)
        (Path(d) / "CORRUPT.json").write_text("not json at all {")
        self.assertIsNone(store.get("CORRUPT"))

    def test_secret_in_primitive_rejected(self):
        from core.knowledge.engine import KnowledgeEngine
        from core.knowledge.store import StoreError
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        engine = KnowledgeEngine(d)
        # Try to bypass by setting secret after creation (should be caught in validation)
        p = engine.create_primitive(domain="d", concept="x", description="y")
        p.provenance.notes = "sk-abcdefghijklmnopqrstuvwxyz12345"
        with self.assertRaises(StoreError):
            engine.update_primitive(p)

    def test_invalid_relation_type(self):
        from core.knowledge.relations import RelationGraph, Relation, RelationError
        g = RelationGraph()
        g.add_primitive(_make_prim(id="A"))
        g.add_primitive(_make_prim(id="B"))
        with self.assertRaises(RelationError):
            g.add_relation("A", Relation(target_id="B", relation_type="INVALID_TYPE"))

    def test_missing_provenance_rejected(self):
        from core.knowledge.engine import KnowledgeEngine
        from core.knowledge.store import StoreError
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        engine = KnowledgeEngine(d)
        p = engine.create_primitive(domain="d", concept="x", description="y")
        p.provenance.created_by = ""
        with self.assertRaises(StoreError):
            engine.update_primitive(p)


# ── Performance smoke ─────────────────────────────────────────────────

class TestPerformance(unittest.TestCase):

    def test_50_primitives_retrieval(self):
        from core.knowledge.engine import KnowledgeEngine
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        engine = KnowledgeEngine(d)
        for i in range(50):
            engine.create_primitive(
                domain=f"domain-{i % 5}",
                concept=f"concept-{i}",
                description=f"description of concept {i} about {['storage','network','process'][i % 3]}",
            )
        t0 = time.time()
        result = engine.retrieve("storage concept", top_k=10)
        elapsed = time.time() - t0
        self.assertLess(elapsed, 1.0, f"retrieval took {elapsed:.2f}s")
        self.assertLessEqual(len(result.scores), 10)


if __name__ == "__main__":
    unittest.main()
