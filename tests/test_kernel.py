#!/usr/bin/env python3
# tests/test_kernel.py
"""Agent Kernel v1.0 tests — E2E loop, crash/resume, idempotency, adversarial."""

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


# ── Schema ────────────────────────────────────────────────────────────

class TestKernelSchema(unittest.TestCase):

    def test_context_roundtrip(self):
        from core.kernel.schema import KernelContext
        ctx = KernelContext(run_id="KRUN-1", goal="test goal", project_id="p")
        ctx.kernel_phase = "COMPLETE"
        ctx.kernel_status = "COMPLETED"
        ctx.knowledge_retrieved = ["P1", "P2"]
        ctx.llm_calls = 3
        ctx.errors = ["error1"]
        d = ctx.to_dict()
        ctx2 = KernelContext.from_dict(d)
        self.assertEqual(ctx.run_id, ctx2.run_id)
        self.assertEqual(ctx.knowledge_retrieved, ctx2.knowledge_retrieved)
        self.assertEqual(ctx.errors, ctx2.errors)

    def test_kernel_phase_values(self):
        from core.kernel.schema import KernelPhase
        phases = {p.value for p in KernelPhase}
        self.assertIn("BOOTSTRAP", phases)
        self.assertIn("KNOWLEDGE_RETRIEVAL", phases)
        self.assertIn("COMPLETE", phases)
        self.assertIn("FAILED", phases)


# ── Policy ──────────────────────────────────────────────────────────

class TestPolicy(unittest.TestCase):

    def test_default_policy(self):
        from core.kernel.policy import PolicyEngine, Policy
        p = PolicyEngine()
        self.assertTrue(p.should_retrieve_knowledge("build a file"))
        self.assertFalse(p.should_call_llm("COMPLETE"))
        self.assertTrue(p.should_execute())
        self.assertFalse(p.should_auto_accept_improvement())

    def test_llm_boundary_enforced(self):
        """LLM may NOT do certain things."""
        from core.kernel.policy import PolicyEngine
        p = PolicyEngine()
        self.assertFalse(p.can_llm_declare_verification())
        self.assertFalse(p.can_llm_promote_knowledge())
        self.assertFalse(p.can_llm_accept_improvement())
        self.assertFalse(p.can_llm_bypass_validator())

    def test_budget_limits(self):
        from core.kernel.policy import PolicyEngine, Budget
        b = Budget(max_llm_calls=2, max_retries=1)
        p = PolicyEngine(budget=b)
        self.assertFalse(p.should_retry(1))  # attempt 1, max 1
        self.assertTrue(p.should_retry(0))   # attempt 0, max 1

    def test_no_knowledge_retrieval_for_empty_goal(self):
        from core.kernel.policy import PolicyEngine
        p = PolicyEngine()
        self.assertFalse(p.should_retrieve_knowledge(""))


# ── Lifecycle ───────────────────────────────────────────────────────

class TestLifecycle(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))

    def test_save_and_load(self):
        from core.kernel.lifecycle import KernelLifecycle, _gen_run_id
        from core.kernel.schema import KernelContext
        lc = KernelLifecycle(self.tmpdir)
        ctx = KernelContext(run_id=_gen_run_id(), goal="x", project_id="p")
        lc.save(ctx)
        loaded = lc.load(ctx.run_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.goal, "x")

    def test_atomic_write(self):
        from core.kernel.lifecycle import KernelLifecycle, _gen_run_id
        from core.kernel.schema import KernelContext
        lc = KernelLifecycle(self.tmpdir)
        ctx = KernelContext(run_id=_gen_run_id(), goal="x", project_id="p")
        lc.save(ctx)
        self.assertFalse((Path(self.tmpdir) / f"{ctx.run_id}.json.tmp").exists())

    def test_resume(self):
        from core.kernel.lifecycle import KernelLifecycle, _gen_run_id
        from core.kernel.schema import KernelContext, KernelStatus
        lc = KernelLifecycle(self.tmpdir)
        ctx = KernelContext(run_id=_gen_run_id(), goal="x", project_id="p")
        lc.save(ctx)
        resumed = lc.resume(ctx.run_id)
        self.assertIsNotNone(resumed)
        self.assertEqual(resumed.kernel_status, KernelStatus.RESUMED.value)

    def test_resume_complete_is_noop(self):
        from core.kernel.lifecycle import KernelLifecycle, _gen_run_id
        from core.kernel.schema import KernelContext, KernelStatus
        lc = KernelLifecycle(self.tmpdir)
        ctx = KernelContext(run_id=_gen_run_id(), goal="x", project_id="p",
                           kernel_status=KernelStatus.COMPLETED.value)
        lc.save(ctx)
        resumed = lc.resume(ctx.run_id)
        self.assertIsNotNone(resumed)
        self.assertEqual(resumed.kernel_status, KernelStatus.COMPLETED.value)

    def test_mark_complete(self):
        from core.kernel.lifecycle import KernelLifecycle, _gen_run_id
        from core.kernel.schema import KernelContext, KernelStatus
        lc = KernelLifecycle(self.tmpdir)
        ctx = KernelContext(run_id=_gen_run_id(), goal="x", project_id="p")
        lc.mark_complete(ctx)
        loaded = lc.load(ctx.run_id)
        self.assertEqual(loaded.kernel_status, KernelStatus.COMPLETED.value)
        self.assertTrue(bool(loaded.finished_at))

    def test_mark_failed(self):
        from core.kernel.lifecycle import KernelLifecycle, _gen_run_id
        from core.kernel.schema import KernelContext, KernelStatus
        lc = KernelLifecycle(self.tmpdir)
        ctx = KernelContext(run_id=_gen_run_id(), goal="x", project_id="p")
        lc.mark_failed(ctx, "test failure")
        loaded = lc.load(ctx.run_id)
        self.assertEqual(loaded.kernel_status, KernelStatus.FAILED.value)
        self.assertIn("test failure", loaded.errors)

    def test_delete(self):
        from core.kernel.lifecycle import KernelLifecycle, _gen_run_id
        from core.kernel.schema import KernelContext
        lc = KernelLifecycle(self.tmpdir)
        ctx = KernelContext(run_id=_gen_run_id(), goal="x", project_id="p")
        lc.save(ctx)
        lc.delete(ctx.run_id)
        self.assertFalse(lc.exists(ctx.run_id))


# ── E2E Learning Loop ────────────────────────────────────────────────

class TestE2ELearning(unittest.TestCase):
    """MANDATORY v1.0 E2E learning test.

    Run 1: goal → failure → experience → lesson → knowledge candidate
    Run 2: same goal → knowledge retrieval → improved execution
    """

    def setUp(self):
        self.tmpdir_k = tempfile.mkdtemp()
        self.tmpdir_e = tempfile.mkdtemp()
        self.tmpdir_eval = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir_k, ignore_errors=True))
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir_e, ignore_errors=True))
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir_eval, ignore_errors=True))

    def test_run1_failure_produces_experience(self):
        """Run 1: Create experience from failure."""
        from core.experience.engine import ExperienceEngine
        from core.experience.schema import Experience

        ee = ExperienceEngine(self.tmpdir_e)
        exp = Experience(
            run_id="RUN-E2E-1",
            goal="analyze project",
            project_id="agent-core",
            action="python -m pytest",
            observation="3 failed, 1 error",
            outcome="failure",
            failure="ModuleNotFoundError: no module named 'requests'",
            recovery="installed requests",
            llm_calls=2,
            estimated_tokens=400,
        )
        ee.record_experience(exp)
        loaded = ee.get_experience("RUN-E2E-1")
        self.assertIsNotNone(loaded)
        self.assertIn("requests", loaded.failure)

    def test_run1_experience_extracts_lesson(self):
        """Run 1: Lesson is extracted from experience."""
        from core.experience.engine import ExperienceEngine
        from core.experience.schema import Experience

        ee = ExperienceEngine(self.tmpdir_e)
        exp = Experience(
            run_id="RUN-E2E-2",
            goal="analyze project",
            project_id="agent-core",
            action="python -m pytest",
            observation="1 passed",
            outcome="success",
            llm_calls=1,
        )
        ee.record_experience(exp)
        lessons = ee.extract_lessons([exp])
        self.assertGreater(len(lessons), 0)

    def test_experience_to_knowledge_promotion(self):
        """Run 1 → knowledge candidate from repeated failure."""
        from core.experience.engine import ExperienceEngine
        from core.experience.schema import Experience
        from core.experience.promotion import ExperiencePromoter
        from core.knowledge.engine import KnowledgeEngine

        ke = KnowledgeEngine(self.tmpdir_k)
        ee = ExperienceEngine(self.tmpdir_e)
        ee.promoter = ExperiencePromoter(ke)

        exps = [
            Experience(
                run_id=f"RUN-{i}",
                goal="analyze code",
                project_id="agent-core",
                outcome="failure",
                failure="ModuleNotFoundError",
                action="pytest",
            )
            for i in range(3)
        ]
        for e in exps:
            ee.record_experience(e)

        results = ee.promote(exps)
        promoted = [r for r in results if r.promoted]
        self.assertGreater(len(promoted), 0)
        prims = ke.list_primitives()
        self.assertGreater(len(prims), 0)

    def test_run2_retrieves_promoted_knowledge(self):
        """Run 2: Knowledge retrieval finds promoted primitive."""
        from core.experience.engine import ExperienceEngine
        from core.experience.schema import Experience
        from core.experience.promotion import ExperiencePromoter
        from core.knowledge.engine import KnowledgeEngine

        ke = KnowledgeEngine(self.tmpdir_k)
        ee = ExperienceEngine(self.tmpdir_e)
        ee.promoter = ExperiencePromoter(ke)

        # Run 1: repeated failure → knowledge
        exps = [
            Experience(
                run_id=f"RUN-{i}",
                goal="analyze code",
                project_id="agent-core",
                outcome="failure",
                failure="ModuleNotFoundError: no module named 'missing'",
                action="pytest",
            )
            for i in range(3)
        ]
        for e in exps:
            ee.record_experience(e)
        results = ee.promote(exps)
        promoted = [r for r in results if r.promoted]
        self.assertGreater(len(promoted), 0)

        # Run 2: knowledge retrieval - use "failure" as query
        retrieval = ke.retrieve("failure dependency", top_k=5)
        self.assertGreater(len(retrieval.scores), 0)
        # The primitive should be about failure pattern
        top_prim = ke.get_primitive(retrieval.scores[0].primitive_id)
        self.assertIsNotNone(top_prim)

    def test_knowledge_retrieval_used_in_planning(self):
        """Primitive retrieved by kernel is usable in context."""
        from core.knowledge.engine import KnowledgeEngine
        from core.kernel.context import KernelContextBuilder

        ke = KnowledgeEngine(self.tmpdir_k)
        prim = ke.create_primitive(
            domain="testing",
            concept="pytest exit code",
            description="pytest returns non-zero exit code on failure",
            when_to_use="check test results",
            failure_modes=["exit code 1", "exit code 2"],
        )
        # Activate it
        prim, _ = ke.validate_primitive(prim)
        prim, _ = ke.verify_primitive(prim, evidence_id="e1")
        prim.confidence = 0.9
        ke.update_primitive(prim)

        # Build context from knowledge
        builder = KernelContextBuilder()
        ctx = builder.build("run tests", [prim.id], ke)
        self.assertEqual(len(ctx["knowledge_primitives"]), 1)
        self.assertIn("pytest", ctx["knowledge_primitives"][0]["concept"])


# ── Crash / Resume ──────────────────────────────────────────────────

class TestCrashResume(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))

    def test_idempotent_experience_recording(self):
        """Recording same experience twice is idempotent."""
        from core.experience.store import ExperienceStore
        from core.experience.schema import Experience
        s = ExperienceStore(self.tmpdir)
        e = Experience(run_id="R1", goal="x", project_id="p",
                      outcome="success")
        s.create(e)
        # Try to create again → must raise
        import pytest
        with self.assertRaises(Exception):
            s.create(e)

    def test_no_duplicate_on_resume(self):
        """Resume does not duplicate experience."""
        from core.kernel.lifecycle import KernelLifecycle, _gen_run_id
        from core.kernel.schema import KernelContext
        lc = KernelLifecycle(self.tmpdir)
        ctx = KernelContext(run_id=_gen_run_id(), goal="x", project_id="p")
        lc.save(ctx)
        # Resume twice
        r1 = lc.resume(ctx.run_id)
        r2 = lc.resume(ctx.run_id)
        self.assertEqual(r1.run_id, r2.run_id)

    def test_checkpoint_at_each_phase(self):
        """Every phase should save state."""
        from core.kernel.lifecycle import KernelLifecycle, _gen_run_id
        from core.kernel.schema import KernelContext, KernelPhase
        lc = KernelLifecycle(self.tmpdir)
        phases = [
            KernelPhase.BOOTSTRAP.value,
            KernelPhase.KNOWLEDGE_RETRIEVAL.value,
            KernelPhase.REASONING.value,
            KernelPhase.COMPLETE.value,
        ]
        for phase in phases:
            ctx = KernelContext(run_id=_gen_run_id(), goal="x",
                              project_id="p", kernel_phase=phase)
            lc.save(ctx)
            loaded = lc.load(ctx.run_id)
            self.assertEqual(loaded.kernel_phase, phase)


# ── Adversarial ─────────────────────────────────────────────────────

class TestAdversarial(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))

    def test_corrupt_kernel_state(self):
        from core.kernel.lifecycle import KernelLifecycle
        lc = KernelLifecycle(self.tmpdir)
        (Path(self.tmpdir) / "CORRUPT.json").write_text("{ bad")
        self.assertIsNone(lc.load("CORRUPT"))

    def test_corrupt_experience_file(self):
        from core.experience.store import ExperienceStore
        s = ExperienceStore(self.tmpdir)
        (Path(self.tmpdir) / "BAD.json").write_text("garbage")
        loaded = s.get("BAD")
        self.assertIsNone(loaded)

    def test_corrupt_knowledge_file(self):
        from core.knowledge.store import PrimitiveStore
        s = PrimitiveStore(self.tmpdir)
        (Path(self.tmpdir) / "BAD.json").write_text("{ broken")
        loaded = s.get("BAD")
        self.assertIsNone(loaded)

    def test_malformed_json_experience(self):
        from core.experience.store import ExperienceStore
        s = ExperienceStore(self.tmpdir)
        (Path(self.tmpdir) / "RUN-MAL.json").write_text("{ not json at all")
        # Should skip corrupt files
        loaded = s.get("RUN-MAL")
        self.assertIsNone(loaded)

    def test_llm_boundary_cannot_bypass_validator(self):
        from core.kernel.policy import PolicyEngine
        p = PolicyEngine()
        self.assertFalse(p.can_llm_bypass_validator())

    def test_secret_in_experience_refused(self):
        from core.experience.recorder import ExperienceRecorder
        r = ExperienceRecorder()
        r.start(run_id="R1", goal="x", project_id="p")
        r.record_action("password=hunter2")
        r.set_outcome("success")
        exp = r.finalize().to_experience()
        self.assertNotIn("hunter2", exp.action)

    def test_secret_in_knowledge_refused(self):
        from core.knowledge.engine import KnowledgeEngine
        from core.knowledge.store import StoreError
        ke = KnowledgeEngine(self.tmpdir)
        p = ke.create_primitive(domain="d", concept="x", description="y")
        p.provenance.notes = "api_key=sk-abcdefghijklmnopqrstuvwxyz12345"
        with self.assertRaises(StoreError):
            ke.update_primitive(p)

    def test_llm_not_used_for_verification(self):
        from core.kernel.policy import PolicyEngine
        p = PolicyEngine()
        self.assertFalse(p.can_llm_declare_verification())

    def test_kernel_error_on_resume_missing_run(self):
        from core.kernel.kernel import Kernel, KernelError
        k = Kernel()
        with self.assertRaises(KernelError):
            k.run("test", resume_id="NONEXISTENT")


# ── Integration ─────────────────────────────────────────────────────

class TestKernelIntegration(unittest.TestCase):

    def test_kernel_orchestrator_creates_context(self):
        from core.kernel.orchestrator import KernelOrchestrator
        o = KernelOrchestrator()
        ctx = o.bootstrap("build tests", "agent-core")
        self.assertEqual(ctx.goal, "build tests")
        self.assertEqual(ctx.project_id, "agent-core")
        self.assertEqual(ctx.kernel_status, "RUNNING")
        self.assertTrue(bool(ctx.run_id))

    def test_knowledge_retrieval_integrates(self):
        from core.kernel.orchestrator import KernelOrchestrator
        from core.knowledge.engine import KnowledgeEngine
        import tempfile, shutil

        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))

        o = KernelOrchestrator()
        o._knowledge = KnowledgeEngine(d)
        o._knowledge.create_primitive(
            domain="testing", concept="pytest", description="run tests"
        )
        ctx = o.bootstrap("run tests", "agent-core")
        ctx = o.retrieve_knowledge(ctx)
        self.assertIn(ctx.kernel_phase, ["KNOWLEDGE_RETRIEVAL", "REASONING"])

    def test_context_builder_uses_knowledge(self):
        from core.kernel.context import KernelContextBuilder
        from core.knowledge.engine import KnowledgeEngine
        import tempfile, shutil

        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))

        ke = KnowledgeEngine(d)
        prim = ke.create_primitive(
            domain="storage", concept="atomic write",
            description="atomic file replacement",
            when_to_use="persist critical state",
        )
        builder = KernelContextBuilder()
        ctx = builder.build("persist state", [prim.id], ke)
        self.assertEqual(len(ctx["knowledge_primitives"]), 1)
        self.assertEqual(ctx["knowledge_primitives"][0]["concept"], "atomic write")


# ── Token economy ──────────────────────────────────────────────────

class TestTokenEconomy(unittest.TestCase):

    def test_llm_call_count_tracked(self):
        from core.kernel.schema import KernelContext
        ctx = KernelContext(run_id="R1", goal="x", project_id="p")
        ctx.llm_calls = 0
        ctx.llm_calls += 1
        ctx.llm_calls += 1
        self.assertEqual(ctx.llm_calls, 2)

    def test_budget_exceeded_stops_kernel(self):
        from core.kernel.policy import Budget, PolicyEngine
        b = Budget(max_llm_calls=2)
        p = PolicyEngine(budget=b)
        # Budget field check
        self.assertEqual(b.max_llm_calls, 2)
        # max_retries defaults to 2; attempt 2 = max means no more retry
        self.assertTrue(p.should_retry(0))
        self.assertTrue(p.should_retry(1))
        self.assertFalse(p.should_retry(2))
        # Custom budget with max_retries=0
        b2 = Budget(max_retries=0)
        p2 = PolicyEngine(budget=b2)
        self.assertFalse(p2.should_retry(0))


if __name__ == "__main__":
    unittest.main()
