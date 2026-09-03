#!/usr/bin/env python3
# tests/test_experience.py
"""Experience Engine v0.8 tests — schema, persistence, recording, lessons, contradiction, etc."""

import json
import re
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def _make_exp(**kw):
    from core.experience.schema import Experience
    defaults = dict(
        run_id="RUN-00001",
        goal="create file",
        project_id="test",
        action="write_file",
        observation="file created at /tmp/test.txt",
        outcome="success",
    )
    defaults.update(kw)
    return Experience(**defaults)


# ── Schema ────────────────────────────────────────────────────────────

class TestSchema(unittest.TestCase):

    def test_roundtrip(self):
        from core.experience.schema import Experience
        e = _make_exp()
        d = e.to_dict()
        e2 = Experience.from_dict(d)
        self.assertEqual(e.run_id, e2.run_id)
        self.assertEqual(e.goal, e2.goal)
        self.assertEqual(e.action, e2.action)
        self.assertEqual(e.observation, e2.observation)
        self.assertEqual(e.outcome, e2.outcome)

    def test_success_detection(self):
        e = _make_exp(outcome="success")
        self.assertTrue(e.success())
        e2 = _make_exp(outcome="test pass")
        self.assertTrue(e2.success())
        e3 = _make_exp(outcome="failure")
        self.assertFalse(e3.success())

    def test_generate_id(self):
        import time
        from core.experience.schema import generate_experience_id
        i1 = generate_experience_id()
        time.sleep(0.001)  # ensure different ms
        i2 = generate_experience_id()
        self.assertTrue(i1.startswith("EXP-"))
        self.assertTrue(i2.startswith("EXP-"))
        self.assertNotEqual(i1, i2)


# ── Store / persistence ──────────────────────────────────────────────

class TestStore(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))

    def test_create_and_get(self):
        from core.experience.store import ExperienceStore
        s = ExperienceStore(self.tmpdir)
        e = _make_exp()
        s.create(e)
        loaded = s.get("RUN-00001")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.goal, e.goal)

    def test_atomic_write_no_tmp(self):
        from core.experience.store import ExperienceStore
        s = ExperienceStore(self.tmpdir)
        s.create(_make_exp())
        self.assertFalse((Path(self.tmpdir) / "RUN-00001.json.tmp").exists())
        self.assertTrue((Path(self.tmpdir) / "RUN-00001.json").exists())

    def test_duplicate_rejected(self):
        from core.experience.store import ExperienceStore, ExperienceStoreError
        s = ExperienceStore(self.tmpdir)
        s.create(_make_exp())
        with self.assertRaises(ExperienceStoreError):
            s.create(_make_exp())

    def test_run_id_required(self):
        from core.experience.store import ExperienceStore, ExperienceStoreError
        from core.experience.schema import Experience
        s = ExperienceStore(self.tmpdir)
        e = Experience(run_id="", goal="x", project_id="p")
        with self.assertRaises(ExperienceStoreError):
            s.create(e)

    def test_corrupt_returns_none(self):
        from core.experience.store import ExperienceStore
        s = ExperienceStore(self.tmpdir)
        (Path(self.tmpdir) / "CORRUPT.json").write_text("{ broken")
        self.assertIsNone(s.get("CORRUPT"))

    def test_list_all(self):
        from core.experience.store import ExperienceStore
        s = ExperienceStore(self.tmpdir)
        s.create(_make_exp(run_id="RUN-A"))
        s.create(_make_exp(run_id="RUN-B"))
        s.create(_make_exp(run_id="RUN-C"))
        self.assertEqual(len(s.list_all()), 3)

    def test_delete(self):
        from core.experience.store import ExperienceStore
        s = ExperienceStore(self.tmpdir)
        s.create(_make_exp())
        self.assertTrue(s.delete("RUN-00001"))
        self.assertIsNone(s.get("RUN-00001"))
        self.assertEqual(s.count(), 0)

    def test_index_persisted(self):
        from core.experience.store import ExperienceStore
        s = ExperienceStore(self.tmpdir)
        s.create(_make_exp())
        idx_path = Path(self.tmpdir) / "index.json"
        self.assertTrue(idx_path.exists())
        idx = json.loads(idx_path.read_text())
        self.assertIn("RUN-00001", idx.get("experiences", {}))


# ── Recorder ─────────────────────────────────────────────────────────

class TestFailureCategory(unittest.TestCase):

    def test_detect_network(self):
        from core.experience.recorder import FailureCategory
        cat = FailureCategory.detect("Connection refused")
        self.assertEqual(cat, FailureCategory.NETWORK)

    def test_detect_syntax(self):
        from core.experience.recorder import FailureCategory
        cat = FailureCategory.detect("SyntaxError: invalid syntax")
        self.assertEqual(cat, FailureCategory.SYNTAX)

    def test_detect_dependency(self):
        from core.experience.recorder import FailureCategory
        cat = FailureCategory.detect("ModuleNotFoundError: No module named 'foo'")
        self.assertEqual(cat, FailureCategory.DEPENDENCY)

    def test_detect_timeout(self):
        from core.experience.recorder import FailureCategory
        cat = FailureCategory.detect("Operation timed out")
        self.assertEqual(cat, FailureCategory.TIMEOUT)

    def test_detect_test_failure(self):
        from core.experience.recorder import FailureCategory
        cat = FailureCategory.detect("test failed: assertion")
        self.assertEqual(cat, FailureCategory.TEST_FAILURE)

    def test_detect_unknown(self):
        from core.experience.recorder import FailureCategory
        cat = FailureCategory.detect("something vague happened")
        self.assertEqual(cat, FailureCategory.UNKNOWN)

    def test_all_categories_defined(self):
        from core.experience.recorder import FailureCategory
        for cat in [
            FailureCategory.CONFIGURATION, FailureCategory.ENVIRONMENT,
            FailureCategory.NETWORK, FailureCategory.DEPENDENCY,
            FailureCategory.SYNTAX, FailureCategory.TEST_FAILURE,
            FailureCategory.RUNTIME, FailureCategory.TIMEOUT,
            FailureCategory.RESOURCE, FailureCategory.LOGIC,
            FailureCategory.VERIFICATION, FailureCategory.UNKNOWN,
        ]:
            self.assertTrue(cat)


class TestScrubSecrets(unittest.TestCase):

    def test_scrub_api_key(self):
        from core.experience.recorder import _scrub
        s = _scrub("token: sk-abcdefghijklmnopqrstuvwxyz12345")
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz12345", s)
        self.assertIn("REDACTED", s)

    def test_scrub_password(self):
        from core.experience.recorder import _scrub
        s = _scrub("password=hunter2")
        self.assertNotIn("hunter2", s)

    def test_scrub_github_token(self):
        from core.experience.recorder import _scrub
        s = _scrub("ghp_1234567890abcdefghijklmnop")
        self.assertNotIn("ghp_1234567890", s)

    def test_scrub_preserves_normal_text(self):
        from core.experience.recorder import _scrub
        text = "file created successfully at /tmp/test.txt"
        self.assertEqual(_scrub(text), text)


class TestExperienceRecorder(unittest.TestCase):

    def test_recorder_full_lifecycle(self):
        from core.experience.recorder import ExperienceRecorder, FailureCategory
        r = ExperienceRecorder()
        r.start(run_id="RUN-T1", goal="test", project_id="p1", task_id="T-1")
        r.record_action("compile code")
        r.record_observation("build successful")
        r.record_verification("tests passed")
        r.set_outcome("success")
        r.set_metrics(cost=1.5, duration=2.0, llm_calls=3, estimated_tokens=500)
        recorded = r.finalize()
        exp = recorded.to_experience()
        self.assertEqual(exp.run_id, "RUN-T1")
        self.assertEqual(exp.goal, "test")
        self.assertEqual(exp.outcome, "success")
        self.assertEqual(exp.duration, 2.0)
        self.assertIn("compile code", exp.action)
        self.assertIn("build successful", exp.observation)
        self.assertEqual(exp.llm_calls, 3)
        self.assertEqual(exp.estimated_tokens, 500)

    def test_recorder_with_failure(self):
        from core.experience.recorder import ExperienceRecorder, FailureCategory
        r = ExperienceRecorder()
        r.start(run_id="RUN-F1", goal="test", project_id="p1")
        r.record_action("compile")
        r.record_failure(category=FailureCategory.SYNTAX,
                          symptom="SyntaxError: invalid syntax",
                          cause="missing colon",
                          recovery="added colon",
                          evidence="exit=1")
        r.set_outcome("failure")
        recorded = r.finalize()
        exp = recorded.to_experience()
        self.assertEqual(exp.outcome, "failure")
        self.assertIn("SyntaxError", exp.failure)
        self.assertIn("added colon", exp.recovery)
        self.assertIsNotNone(recorded.failure)
        self.assertEqual(recorded.failure.category, FailureCategory.SYNTAX)

    def test_recorder_scrubs_secrets(self):
        from core.experience.recorder import ExperienceRecorder
        r = ExperienceRecorder()
        r.start(run_id="RUN-S1", goal="test", project_id="p1")
        r.record_action("login with sk-abcdefghijklmnopqrstuvwxyz12345")
        r.record_observation("failed: password=secret123")
        r.set_outcome("failure")
        exp = r.finalize().to_experience()
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", exp.action)
        self.assertNotIn("secret123", exp.observation)


class TestRecordFromRunState(unittest.TestCase):

    def test_record_from_run_state(self):
        from core.experience.recorder import record_from_run_state
        run_state = {
            "run_id": "RUN-100",
            "goal": "build and test",
            "project_id": "myapp",
            "status": "RUNNING",
            "metrics": {"llm_calls": 5, "estimated_tokens": 1000},
        }
        task_outcomes = [
            {
                "title": "compile",
                "result": "compile success",
                "verification": {"verified": True},
                "error": "",
            },
            {
                "title": "test",
                "result": "5 passed",
                "verification": {"verified": True},
                "error": "",
            },
        ]
        exp = record_from_run_state(run_state, task_outcomes)
        self.assertEqual(exp.run_id, "RUN-100")
        self.assertEqual(exp.llm_calls, 5)
        self.assertEqual(exp.estimated_tokens, 1000)
        self.assertIn("compile", exp.action)
        self.assertIn("5 passed", exp.observation)

    def test_record_from_run_state_with_failure(self):
        from core.experience.recorder import record_from_run_state, FailureCategory
        run_state = {
            "run_id": "RUN-101",
            "goal": "deploy",
            "project_id": "myapp",
            "status": "FAILED",
            "metrics": {"llm_calls": 2, "estimated_tokens": 400},
        }
        task_outcomes = [
            {"title": "deploy", "result": "", "verification": {},
             "error": "Connection refused: cannot reach server"},
        ]
        exp = record_from_run_state(run_state, task_outcomes)
        self.assertIn("Connection refused", exp.failure)


# ── Normalizer ───────────────────────────────────────────────────────

class TestNormalizer(unittest.TestCase):

    def test_scrub_normalizer(self):
        from core.experience.normalizer import scrub
        s = scrub("api_key=sk-abcdefghijklmnopqrstuvwxyz12345")
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", s)

    def test_normalize_detects_exit_code(self):
        from core.experience.normalizer import normalize_observation
        obs = normalize_observation("command failed with exit code 1")
        self.assertEqual(obs.exit_code, 1)
        self.assertTrue(obs.is_error)

    def test_normalize_detects_duration(self):
        from core.experience.normalizer import normalize_observation
        obs = normalize_observation("test passed after 3.5 seconds")
        self.assertEqual(obs.duration_seconds, 3.5)

    def test_normalize_detects_tags(self):
        from core.experience.normalizer import normalize_observation
        obs = normalize_observation("file write to /tmp/x.txt")
        self.assertIn("file", obs.tags)

    def test_normalize_observations_batch(self):
        from core.experience.normalizer import normalize_observations
        out = normalize_observations(["a", "b", "c"])
        self.assertEqual(len(out), 3)


# ── Analyzer ─────────────────────────────────────────────────────────

class TestAnalyzer(unittest.TestCase):

    def test_empty(self):
        from core.experience.analyzer import ExperienceAnalyzer
        a = ExperienceAnalyzer()
        m = a.analyze([])
        self.assertEqual(m.total, 0)
        self.assertEqual(m.success_rate, 0.0)

    def test_success_rate(self):
        from core.experience.analyzer import ExperienceAnalyzer
        a = ExperienceAnalyzer()
        exps = [
            _make_exp(run_id="R1", outcome="success"),
            _make_exp(run_id="R2", outcome="success"),
            _make_exp(run_id="R3", outcome="failure"),
        ]
        m = a.analyze(exps)
        self.assertEqual(m.total, 3)
        self.assertEqual(m.success_count, 2)
        self.assertEqual(m.failure_count, 1)
        self.assertAlmostEqual(m.success_rate, 2/3)

    def test_recovery_rate(self):
        from core.experience.analyzer import ExperienceAnalyzer
        a = ExperienceAnalyzer()
        exps = [
            _make_exp(run_id="R1", outcome="failure", failure="boom", recovery="restarted"),
            _make_exp(run_id="R2", outcome="failure", failure="boom", recovery=""),
            _make_exp(run_id="R3", outcome="success"),
        ]
        m = a.analyze(exps)
        # recovery is 1 out of 2 failures
        self.assertEqual(m.recovery_count, 1)
        self.assertAlmostEqual(m.recovery_rate, 0.5)

    def test_by_failure_category(self):
        from core.experience.analyzer import ExperienceAnalyzer
        a = ExperienceAnalyzer()
        exps = [
            _make_exp(run_id="R1", outcome="failure", failure="Connection refused"),
            _make_exp(run_id="R2", outcome="failure", failure="SyntaxError: x"),
            _make_exp(run_id="R3", outcome="success"),
        ]
        grouped = a.by_failure_category(exps)
        self.assertIn("SUCCESS", grouped)
        self.assertIn("NETWORK", grouped)
        self.assertIn("SYNTAX", grouped)

    def test_by_domain(self):
        from core.experience.analyzer import ExperienceAnalyzer
        a = ExperienceAnalyzer()
        exps = [
            _make_exp(run_id="R1", goal="test the network code"),
            _make_exp(run_id="R2", goal="build the project"),
        ]
        by_d = a.by_domain(exps)
        self.assertIn("testing", by_d)
        self.assertIn("build", by_d)

    def test_total_tokens_and_duration(self):
        from core.experience.analyzer import ExperienceAnalyzer
        a = ExperienceAnalyzer()
        exps = [
            _make_exp(run_id="R1", llm_calls=2, estimated_tokens=300, duration=1.5),
            _make_exp(run_id="R2", llm_calls=4, estimated_tokens=700, duration=2.5),
        ]
        m = a.analyze(exps)
        self.assertEqual(m.total_llm_calls, 6)
        self.assertEqual(m.total_tokens, 1000)
        self.assertEqual(m.total_duration, 4.0)
        self.assertAlmostEqual(m.avg_duration, 2.0)


# ── Lesson Engine ────────────────────────────────────────────────────

class TestLessonEngine(unittest.TestCase):

    def test_extract_first_observation(self):
        from core.experience.lesson import LessonEngine, LessonType
        e = LessonEngine()
        exp = _make_exp(action="write_file")
        lesson = e.extract(exp)
        self.assertEqual(lesson.lesson_type, LessonType.FIRST_OBSERVATION)
        self.assertEqual(lesson.evidence_count, 1)
        self.assertLess(lesson.confidence, 0.5)

    def test_extract_creates_unique_id(self):
        from core.experience.lesson import LessonEngine
        e = LessonEngine()
        l1 = e.extract(_make_exp(run_id="R1", action="write"))
        l2 = e.extract(_make_exp(run_id="R2", action="read"))
        self.assertNotEqual(l1.lesson_id, l2.lesson_id)

    def test_record_observation_increments_evidence(self):
        from core.experience.lesson import LessonEngine
        e = LessonEngine()
        # Use same run_id to get same lesson_id
        l1 = e.record_observation(_make_exp(run_id="R1"), "write", "write file", "writes work")
        self.assertEqual(l1.evidence_count, 1)
        conf1 = l1.confidence
        self.assertEqual(conf1, 0.2)  # initial confidence on creation
        l2 = e.record_observation(_make_exp(run_id="R1"), "write", "write file", "writes work again")
        # Same run_id → same lesson_id (same object)
        self.assertIs(l1, l2)
        self.assertEqual(l2.evidence_count, 2)
        self.assertGreater(l2.confidence, conf1)  # 0.4 > 0.2

    def test_contradiction_detection(self):
        from core.experience.lesson import LessonEngine, LessonType
        e = LessonEngine()
        l1 = e.record_observation(_make_exp(run_id="R1"), "x", "t1", "d1")
        # Force a different lesson type
        l1.lesson_type = LessonType.FIRST_OBSERVATION
        l2 = e.record_observation(_make_exp(run_id="R2"), "x", "t2", "d2")
        l2.lesson_type = LessonType.CONTRADICTORY_OBSERVATION
        detected = e.detect_contradiction(l1.lesson_id, l2.lesson_id)
        self.assertTrue(detected)
        self.assertIn(l2.lesson_id, l1.contradiction_ids)

    def test_resolve_contradiction(self):
        from core.experience.lesson import LessonEngine, LessonType
        e = LessonEngine()
        l1 = e.record_observation(_make_exp(run_id="R1"), "x", "t1", "d1")
        l2 = e.record_observation(_make_exp(run_id="R2"), "x", "t2", "d2")
        l1.lesson_type = LessonType.FIRST_OBSERVATION
        l2.lesson_type = LessonType.CONTRADICTORY_OBSERVATION
        e.detect_contradiction(l1.lesson_id, l2.lesson_id)
        # Resolve
        resolved = e.resolve_contradiction(l1.lesson_id, "later evidence")
        self.assertTrue(resolved.resolved)
        self.assertGreaterEqual(resolved.confidence, 0.2)

    def test_lessons_summary(self):
        from core.experience.lesson import LessonEngine
        e = LessonEngine()
        e.extract(_make_exp(run_id="R1"))
        e.extract(_make_exp(run_id="R2"))
        s = e.lessons_summary()
        self.assertEqual(s["total"], 2)
        self.assertIn("FIRST_OBSERVATION", s["by_type"])

    def test_lesson_roundtrip(self):
        from core.experience.lesson import Lesson
        l = Lesson(
            lesson_id="L-1",
            title="t",
            description="d",
            lesson_type="FIRST_OBSERVATION",
            source_experience_id="R1",
            evidence_count=2,
        )
        d = l.to_dict()
        l2 = Lesson.from_dict(d)
        self.assertEqual(l.lesson_id, l2.lesson_id)
        self.assertEqual(l.evidence_count, l2.evidence_count)


# ── Experience Learner ───────────────────────────────────────────────

class TestLearner(unittest.TestCase):

    def test_empty_learn(self):
        from core.experience.learner import ExperienceLearner
        l = ExperienceLearner()
        cands = l.learn([])
        self.assertEqual(cands, [])

    def test_learn_from_failures(self):
        from core.experience.learner import ExperienceLearner
        l = ExperienceLearner()
        exps = [
            _make_exp(run_id="R1", outcome="failure", failure="Connection refused"),
            _make_exp(run_id="R2", outcome="failure", failure="Connection refused again"),
            _make_exp(run_id="R3", outcome="failure", failure="Connection refused third"),
        ]
        cands = l.learn(exps)
        self.assertGreater(len(cands), 0)
        # At least one candidate should be a failure-network one
        found = any("network" in c.primitive.concept for c in cands)
        self.assertTrue(found)

    def test_learn_from_success(self):
        from core.experience.learner import ExperienceLearner
        l = ExperienceLearner()
        exps = [
            _make_exp(run_id="R1", outcome="success"),
            _make_exp(run_id="R2", outcome="success"),
        ]
        cands = l.learn(exps)
        self.assertGreater(len(cands), 0)
        # The success candidate should exist
        success_cand = [c for c in cands if "successful" in c.primitive.concept]
        self.assertGreater(len(success_cand), 0)

    def test_single_experience_no_candidate(self):
        from core.experience.learner import ExperienceLearner
        l = ExperienceLearner()
        # Only 1 experience: failure pattern needs >= 2
        cands = l.learn([_make_exp(run_id="R1", outcome="failure", failure="boom")])
        # No failure candidate (insufficient evidence)
        failure_cands = [c for c in cands if c.primitive.concept.startswith("failure_")]
        self.assertEqual(len(failure_cands), 0)

    def test_reject_candidate(self):
        from core.experience.learner import ExperienceLearner
        l = ExperienceLearner()
        exps = [
            _make_exp(run_id="R1", outcome="success"),
            _make_exp(run_id="R2", outcome="success"),
        ]
        cands = l.learn(exps)
        if cands:
            l.reject_candidate(cands[0], "test")
            self.assertEqual(cands[0].status, "REJECTED")


# ── Knowledge Reuse Integration ──────────────────────────────────────

class TestKnowledgeReuse(unittest.TestCase):

    def setUp(self):
        self.tmpdir_k = tempfile.mkdtemp()
        self.tmpdir_e = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir_k, ignore_errors=True))
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir_e, ignore_errors=True))

    def test_experience_promotes_to_knowledge(self):
        from core.knowledge.engine import KnowledgeEngine
        from core.experience.engine import ExperienceEngine
        from core.experience.schema import Experience
        ke = KnowledgeEngine(self.tmpdir_k)
        ee = ExperienceEngine(self.tmpdir_e)
        # Override promoter to use our knowledge engine
        from core.experience.promotion import ExperiencePromoter
        ee.promoter = ExperiencePromoter(ke)
        # Add some failure experiences
        exps = [
            _make_exp(run_id="R1", outcome="failure", failure="Connection refused"),
            _make_exp(run_id="R2", outcome="failure", failure="Connection refused again"),
            _make_exp(run_id="R3", outcome="failure", failure="Connection refused third"),
        ]
        for e in exps:
            ee.record_experience(e)
        # Promote
        results = ee.promote(exps)
        self.assertGreater(len(results), 0)
        # Some should be promoted
        promoted = [r for r in results if r.promoted]
        self.assertGreater(len(promoted), 0)
        # New primitives should exist in knowledge engine
        prims = ke.list_primitives()
        self.assertGreater(len(prims), 0)

    def test_second_run_retrieves_primitive(self):
        """End-to-end: after promotion, the primitive is retrievable."""
        from core.knowledge.engine import KnowledgeEngine
        from core.experience.engine import ExperienceEngine
        ke = KnowledgeEngine(self.tmpdir_k)
        ee = ExperienceEngine(self.tmpdir_e)
        from core.experience.promotion import ExperiencePromoter
        ee.promoter = ExperiencePromoter(ke)

        exps = [
            _make_exp(run_id="R1", outcome="failure", failure="Connection refused"),
            _make_exp(run_id="R2", outcome="failure", failure="Connection refused again"),
        ]
        for e in exps:
            ee.record_experience(e)
        results = ee.promote(exps)

        # Now retrieve
        result = ke.retrieve("connection network", top_k=5)
        self.assertGreater(len(result.scores), 0)


# ── Engine integration ───────────────────────────────────────────────

class TestEngine(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))

    def test_full_engine_flow(self):
        from core.experience.engine import ExperienceEngine
        e = ExperienceEngine(self.tmpdir)
        e.record_experience(_make_exp(run_id="R1", outcome="success"))
        e.record_experience(_make_exp(run_id="R2", outcome="failure",
                                       failure="Connection refused"))
        e.record_experience(_make_exp(run_id="R3", outcome="failure",
                                       failure="Connection refused"))
        exps = e.list_experiences()
        self.assertEqual(len(exps), 3)
        metrics = e.analyze(exps)
        self.assertEqual(metrics.total, 3)
        lessons = e.extract_lessons(exps)
        self.assertEqual(len(lessons), 3)
        stats = e.stats()
        self.assertEqual(stats.total_experiences, 3)
        self.assertEqual(stats.total_lessons, 3)

    def test_no_secrets_persisted(self):
        from core.experience.recorder import ExperienceRecorder
        from core.experience.engine import ExperienceEngine
        from core.experience.schema import Experience
        r = ExperienceRecorder()
        r.start(run_id="R-SECRET", goal="test", project_id="p1")
        r.record_action("token: sk-abcdefghijklmnopqrstuvwxyz12345")
        r.record_observation("api_key=ghp_1234567890abcdefghij")
        r.record_failure(category="RUNTIME", symptom="api_key=ghp_1234567890abcdefghij",
                          cause="bad creds", recovery="rotated")
        r.set_outcome("failure")
        exp = r.finalize().to_experience()
        self.assertIn("[REDACTED]", exp.action)
        self.assertIn("[REDACTED]", exp.failure)
        # Also: observation has secret; failure has it; both should be redacted
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", exp.action)
        self.assertNotIn("ghp_1234567890", exp.failure)


# ── Adversarial ──────────────────────────────────────────────────────

class TestAdversarial(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))

    def test_corrupt_experience_file(self):
        from core.experience.store import ExperienceStore
        s = ExperienceStore(self.tmpdir)
        (Path(self.tmpdir) / "BAD.json").write_text("garbage")
        self.assertIsNone(s.get("BAD"))
        # list_all should not crash
        self.assertEqual(len(s.list_all()), 0)

    def test_missing_run_id(self):
        from core.experience.store import ExperienceStore, ExperienceStoreError
        from core.experience.schema import Experience
        s = ExperienceStore(self.tmpdir)
        with self.assertRaises(ExperienceStoreError):
            s.create(Experience(run_id="", goal="x", project_id="p"))

    def test_duplicate_experience(self):
        from core.experience.store import ExperienceStore, ExperienceStoreError
        s = ExperienceStore(self.tmpdir)
        s.create(_make_exp())
        with self.assertRaises(ExperienceStoreError):
            s.create(_make_exp())

    def test_contradictory_lesson_doesnt_overwrite(self):
        from core.experience.lesson import LessonEngine, LessonType
        e = LessonEngine()
        l1 = e.record_observation(_make_exp(run_id="R1"), "x", "t1", "d1")
        l2 = e.record_observation(_make_exp(run_id="R2"), "x", "t2", "d2")
        l1.lesson_type = LessonType.FIRST_OBSERVATION
        l2.lesson_type = LessonType.CONTRADICTORY_OBSERVATION
        e.detect_contradiction(l1.lesson_id, l2.lesson_id)
        # Both should still exist
        self.assertIsNotNone(e.get_lesson(l1.lesson_id))
        self.assertIsNotNone(e.get_lesson(l2.lesson_id))


# ── Performance smoke ────────────────────────────────────────────────

class TestPerformance(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))

    def test_100_experiences(self):
        from core.experience.store import ExperienceStore
        from core.experience.analyzer import ExperienceAnalyzer
        s = ExperienceStore(self.tmpdir)
        for i in range(100):
            s.create(_make_exp(run_id=f"RUN-{i:05d}",
                                outcome="success" if i % 3 == 0 else "failure",
                                failure="boom" if i % 3 else ""))
        t0 = time.time()
        exps = s.list_all()
        a = ExperienceAnalyzer()
        m = a.analyze(exps)
        elapsed = time.time() - t0
        self.assertEqual(len(exps), 100)
        self.assertEqual(m.total, 100)
        self.assertLess(elapsed, 2.0, f"took {elapsed:.2f}s")


if __name__ == "__main__":
    unittest.main()
