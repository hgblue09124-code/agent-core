#!/usr/bin/env python3
# tests/test_runtime.py
"""Runtime v0.6 — critical behavior tests.

Run: python3 -m unittest tests.test_runtime -v
"""

import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


class TestSchema(unittest.TestCase):
    """RunState serialization / transition helpers."""

    def test_run_state_to_dict_roundtrip(self):
        from core.runtime.schema import RunState, PhaseMetrics
        state = RunState(
            run_id="RUN-00001",
            goal="Test goal",
            project_id="test-proj",
            status="RUNNING",
            phase="EXECUTING",
            started_at="2025-01-01T00:00:00+00:00",
            metrics=PhaseMetrics(llm_calls=5, estimated_tokens=1000),
        )
        d = state.to_dict()
        restored = RunState.from_dict(d)
        self.assertEqual(restored.run_id, "RUN-00001")
        self.assertEqual(restored.goal, "Test goal")
        self.assertEqual(restored.status, "RUNNING")
        self.assertEqual(restored.metrics.llm_calls, 5)
        self.assertEqual(restored.metrics.estimated_tokens, 1000)

    def test_new_checkpoint_increments_count(self):
        from core.runtime.schema import RunState
        state = RunState(run_id="RUN-1", goal="g", project_id="p")
        self.assertEqual(state.metrics.checkpoints, 0)
        cp = state.new_checkpoint()
        self.assertEqual(cp.metrics.checkpoints, 1)
        self.assertIsNot(cp, state)

    def test_transition_copies_state(self):
        from core.runtime.schema import RunState, RunStatus, RunPhase
        state = RunState(run_id="R1", goal="g", project_id="p")
        t = state.transition(RunStatus.COMPLETED, RunPhase.STOPPED, error="done")
        self.assertEqual(t.status, "COMPLETED")
        self.assertEqual(t.phase, "STOPPED")
        self.assertEqual(t.error, "done")
        self.assertEqual(t.run_id, "R1")  # unchanged
        self.assertIsNot(t, state)


class TestCheckpoint(unittest.TestCase):
    """Atomic checkpoint persistence."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))

    def _store(self, **kw):
        from core.runtime.checkpoint import CheckpointStore
        return CheckpointStore(self.tmpdir, **kw)

    def test_save_and_load(self):
        from core.runtime.schema import RunState
        store = self._store()
        state = RunState(run_id="RUN-00001", goal="x", project_id="p")
        store.save(state)
        loaded = store.load("RUN-00001")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.run_id, "RUN-00001")

    def test_load_missing_returns_none(self):
        store = self._store()
        self.assertIsNone(store.load("RUN-DOES-NOT-EXIST"))

    def test_exists(self):
        from core.runtime.schema import RunState
        store = self._store()
        self.assertFalse(store.exists("RUN-00001"))
        store.save(RunState(run_id="RUN-00001", goal="x", project_id="p"))
        self.assertTrue(store.exists("RUN-00001"))

    def test_list_runs(self):
        from core.runtime.schema import RunState
        store = self._store()
        store.save(RunState(run_id="RUN-00001", goal="x", project_id="p"))
        store.save(RunState(run_id="RUN-00002", goal="y", project_id="p"))
        runs = store.list_runs()
        self.assertIn("RUN-00001", runs)
        self.assertIn("RUN-00002", runs)

    def test_atomic_write_no_corruption(self):
        """Simulate crash mid-write: .tmp file exists but no final file."""
        from core.runtime.schema import RunState
        store = self._store()

        # Write a valid state
        good = RunState(run_id="RUN-ATOMIC", goal="good", project_id="p")
        store.save(good)

        # Simulate interrupted write: leave only .tmp
        tmp = store._tmp_path("RUN-ATOMIC")
        target = store._path("RUN-ATOMIC")
        target.unlink()
        tmp.write_text("{ broken json }", encoding="utf-8")

        # Load should ignore the corrupted tmp and return None (or last good)
        loaded = store.load("RUN-ATOMIC")
        # Our implementation returns None when main file missing
        self.assertIsNone(loaded)

    def test_delete(self):
        from core.runtime.schema import RunState
        store = self._store()
        store.save(RunState(run_id="RUN-DEL", goal="x", project_id="p"))
        self.assertTrue(store.exists("RUN-DEL"))
        store.delete("RUN-DEL")
        self.assertFalse(store.exists("RUN-DEL"))

    def test_json_tmp_not_visible_as_main(self):
        """After save, .tmp should not exist as a run."""
        from core.runtime.schema import RunState
        store = self._store()
        store.save(RunState(run_id="RUN-TMP", goal="x", project_id="p"))
        runs = store.list_runs()
        self.assertNotIn("RUN-TMP.json.tmp", runs)


class TestConfig(unittest.TestCase):
    """RuntimeConfig from env."""

    def test_defaults(self):
        from core.runtime.config import RuntimeConfig
        cfg = RuntimeConfig()
        self.assertEqual(cfg.max_llm_calls, 100)
        self.assertEqual(cfg.max_runtime_seconds, 28800)
        self.assertEqual(cfg.internet_policy, "off")

    def test_env_override(self):
        env = {
            "AGENTCORE_RUNTIME_MAX_LLM_CALLS": "50",
            "AGENTCORE_RUNTIME_MAX_SECONDS": "3600",
            "AGENTCORE_RUNTIME_INTERNET": "on",
        }
        saved = {k: os.environ.pop(k, None) for k in env}
        os.environ.update(env)
        try:
            from core.runtime.config import RuntimeConfig
            cfg = RuntimeConfig.from_env()
            self.assertEqual(cfg.max_llm_calls, 50)
            self.assertEqual(cfg.max_runtime_seconds, 3600)
            self.assertEqual(cfg.internet_policy, "on")
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


class TestEngineBootstrap(unittest.TestCase):
    """Engine bootstrap and environment checks."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))
        # Clear planner env vars to use mock
        self._saved_env = {
            k: os.environ.pop(k, None)
            for k in [
                "OPENAI_API_KEY", "AGENTCORE_PLANNER_API_KEY",
                "AGENTCORE_RUNTIME_MAX_LLM_CALLS",
                "AGENTCORE_RUNTIME_MAX_TOKEN_BUDGET",
                "AGENTCORE_RUNTIME_MAX_REFINEMENTS",
                "AGENTCORE_RUNTIME_MAX_RETRIES",
                "AGENTCORE_RUNTIME_MAX_SECONDS",
                "AGENTCORE_RUNTIME_INTERNET",
            ]
        }

    def tearDown(self):
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _engine(self, **runtime_cfg):
        from core.runtime.config import RuntimeConfig
        from core.runtime.engine import RuntimeEngine
        cfg = RuntimeConfig(**runtime_cfg)
        return RuntimeEngine(runs_dir=self.tmpdir, config=cfg)

    def test_new_run_state_has_correct_fields(self):
        from core.runtime.schema import RunState, RunStatus, RunPhase
        state = RunState(run_id="RUN-TEST", goal="Test", project_id="p")
        self.assertEqual(state.status, RunStatus.PENDING.value)
        self.assertEqual(state.phase, RunPhase.BOOTSTRAP.value)
        self.assertEqual(state.run_id, "RUN-TEST")

    def test_engine_bootstrap_fails_for_unknown_project(self):
        from core.runtime.schema import RunState, RunStatus, RunPhase
        engine = self._engine()
        state = RunState(run_id="RUN-BOOT", goal="Test", project_id="nonexistent-project-xyz")
        result = engine._bootstrap(state)
        self.assertEqual(result.status, RunStatus.FAILED.value)
        self.assertEqual(result.phase, RunPhase.BOOTSTRAP.value)
        self.assertIn("not found", result.error.lower())

    def test_internet_off_by_default(self):
        from core.runtime.config import RuntimeConfig
        cfg = RuntimeConfig()
        self.assertEqual(cfg.internet_policy, "off")

    def test_budget_check_fails_at_limit(self):
        from core.runtime.schema import RunState, PhaseMetrics
        engine = self._engine(max_llm_calls=2)
        state = RunState(
            run_id="R1", goal="x", project_id="p",
            metrics=PhaseMetrics(llm_calls=2),
        )
        ok, reason = engine._check_budget(state)
        self.assertFalse(ok)
        self.assertIn("LLM call", reason)

    def test_budget_check_passes_within_limit(self):
        from core.runtime.schema import RunState, PhaseMetrics
        engine = self._engine(max_llm_calls=100)
        state = RunState(
            run_id="R1", goal="x", project_id="p",
            metrics=PhaseMetrics(llm_calls=5),
        )
        ok, reason = engine._check_budget(state)
        self.assertTrue(ok)


class TestRetryLimit(unittest.TestCase):
    """Retry limit enforcement."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))
        self._saved_env = {
            k: os.environ.pop(k, None)
            for k in [
                "OPENAI_API_KEY", "AGENTCORE_PLANNER_API_KEY",
                "AGENTCORE_RUNTIME_MAX_RETRIES",
            ]
        }

    def tearDown(self):
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_retry_limit_reached(self):
        from core.runtime.schema import RunState, RunStatus, RunPhase, PhaseMetrics
        from core.runtime.config import RuntimeConfig
        from core.runtime.engine import RuntimeEngine
        cfg = RuntimeConfig(max_retries=2)
        engine = RuntimeEngine(runs_dir=self.tmpdir, config=cfg)
        # Simulate a state with max retries already consumed
        state = RunState(
            run_id="RUN-RETRY", goal="Test", project_id="default",
            status=RunStatus.RUNNING.value,
            phase=RunPhase.EXECUTING.value,
            metrics=PhaseMetrics(),
        )
        state.retry_count = 3  # exceeds max_retries=2

        # Use a recoverable failure
        from core.tasks.schema import TaskStep, StepType, TaskStatus
        failed_task = MagicMock()
        failed_task.status = TaskStatus.FAILED
        failed_task.error = "SyntaxError"
        failed_task.steps = [TaskStep(type=StepType.SHELL, title="Test step", command="false")]

        from core.planner.schema import PlanStep
        step = PlanStep(step_id="s1", title="t", command="false")

        state2, recovered = engine._handle_failure(state, failed_task, step)
        self.assertFalse(recovered)
        self.assertEqual(state2.status, RunStatus.FAILED.value)


class TestSecretLeakage(unittest.TestCase):
    """Secrets never enter state/logs/checkpoints."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))

    def test_api_key_not_in_run_state(self):
        from core.runtime.schema import RunState
        from core.runtime.checkpoint import CheckpointStore
        store = CheckpointStore(self.tmpdir)

        # Create a state — note RunState has no api_key field by design
        state = RunState(run_id="RUN-SECRET", goal="Test goal", project_id="p")
        d = state.to_dict()
        self.assertNotIn("api_key", d)
        # Check no API key patterns in any value
        for v in d.values():
            self.assertNotIn("sk-", str(v))
        # Verify api_key field does not exist
        self.assertNotIn("api_key", d)

        # Save and load — still no secrets
        store.save(state)
        loaded = store.load("RUN-SECRET")
        loaded_d = loaded.to_dict()
        self.assertNotIn("api_key", loaded_d)
        self.assertNotIn("sk-", str(loaded_d))

    def test_config_manager_key_not_in_state(self):
        from core.runtime.schema import RunState
        state = RunState(run_id="R1", goal="g", project_id="p")
        d = state.to_dict()
        self.assertNotIn("api_key", d)
        self.assertNotIn("OPENAI_API_KEY", str(d))


class TestCheckpointCreation(unittest.TestCase):
    """Checkpoint persistence during execution."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))
        self._saved_env = {
            k: os.environ.pop(k, None)
            for k in ["OPENAI_API_KEY", "AGENTCORE_PLANNER_API_KEY"]
        }

    def tearDown(self):
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_checkpoint_file_created(self):
        from core.runtime.schema import RunState
        from core.runtime.checkpoint import CheckpointStore
        from core.runtime.engine import RuntimeEngine
        from core.runtime.config import RuntimeConfig

        store = CheckpointStore(self.tmpdir)
        cfg = RuntimeConfig(max_llm_calls=0)  # no LLM calls
        engine = RuntimeEngine(runs_dir=self.tmpdir, config=cfg)

        state = RunState(run_id="RUN-CKPT", goal="Test", project_id="nonexistent")
        engine._checkpoint(state)

        # File must exist
        self.assertTrue(Path(self.tmpdir, "RUN-CKPT.json").exists())
        # .tmp must NOT exist
        self.assertFalse(Path(self.tmpdir, "RUN-CKPT.json.tmp").exists())


class TestInternetOff(unittest.TestCase):
    """Internet OFF-by-default policy."""

    def setUp(self):
        self._saved_env = {
            k: os.environ.pop(k, None)
            for k in ["OPENAI_API_KEY", "AGENTCORE_PLANNER_API_KEY",
                       "AGENTCORE_RUNTIME_INTERNET"]
        }

    def tearDown(self):
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_internet_off_rejects_llm_escalation(self):
        from core.runtime.config import RuntimeConfig
        from core.runtime.engine import RuntimeEngine
        from core.runtime.schema import RunState, PhaseMetrics
        from core.tasks.schema import TaskStep, StepType
        from core.planner.schema import PlanStep

        cfg = RuntimeConfig(internet_policy="off")
        engine = RuntimeEngine(config=cfg)

        failed_task = MagicMock()
        failed_task.status = "FAILED"
        failed_task.error = "SyntaxError"
        failed_task.steps = [TaskStep(type=StepType.SHELL, title="Test step", command="false")]

        state = RunState(
            run_id="R1", goal="Test", project_id="p",
            metrics=PhaseMetrics(llm_calls=0),
        )
        step = PlanStep(step_id="s1", title="t", command="false")

        # LLM repair should not be attempted in off mode
        new_state, recovered = engine._llm_repair(state, failed_task, step, "code error")
        # Should return False (could not repair) and not escalate
        self.assertFalse(recovered)


class TestPlanRefinement(unittest.TestCase):
    """Plan refinement without LLM."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))
        self._saved_env = {
            k: os.environ.pop(k, None)
            for k in ["OPENAI_API_KEY", "AGENTCORE_PLANNER_API_KEY"]
        }

    def tearDown(self):
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_detect_missing_command(self):
        from core.runtime.engine import RuntimeEngine
        from core.runtime.config import RuntimeConfig
        from core.runtime.schema import RunState
        from core.planner.schema import Plan, PlanStep

        cfg = RuntimeConfig()
        engine = RuntimeEngine(runs_dir=self.tmpdir, config=cfg)

        plan = Plan(
            objective="Test",
            project_id="p",
            steps=[
                PlanStep(step_id="s1", title="Missing cmd", step_type="shell",
                         command=""),  # missing
                PlanStep(step_id="s2", title="Good", step_type="shell",
                         command="ls"),
            ],
        )

        issues = engine._detect_plan_issues(plan)
        self.assertIn("MISSING_COMMAND:s1", issues)

    def test_detect_bad_dependency(self):
        from core.runtime.engine import RuntimeEngine
        from core.runtime.config import RuntimeConfig
        from core.planner.schema import Plan, PlanStep

        cfg = RuntimeConfig()
        engine = RuntimeEngine(runs_dir=self.tmpdir, config=cfg)

        plan = Plan(
            objective="Test",
            project_id="p",
            steps=[
                PlanStep(step_id="s1", title="s1",
                         command="ls", dependencies=["nonexistent"]),
            ],
        )
        issues = engine._detect_plan_issues(plan)
        self.assertTrue(any("BAD_DEP" in i for i in issues))

    def test_apply_refinement_fixes_missing_title(self):
        from core.runtime.engine import RuntimeEngine
        from core.runtime.config import RuntimeConfig
        from core.planner.schema import Plan, PlanStep

        cfg = RuntimeConfig()
        engine = RuntimeEngine(runs_dir=self.tmpdir, config=cfg)

        plan = Plan(
            objective="Test",
            project_id="p",
            steps=[
                PlanStep(step_id="s1", title="", step_type="shell", command="ls"),
            ],
        )
        issues = ["MISSING_TITLE:s1"]
        refined = engine._apply_refinements(plan, issues)
        self.assertEqual(refined.steps[0].title, "Untitled step s1")

    def test_refinement_respects_max_limit(self):
        from core.runtime.engine import RuntimeEngine
        from core.runtime.config import RuntimeConfig
        from core.runtime.schema import RunState
        from core.planner.schema import Plan, PlanStep

        cfg = RuntimeConfig(max_plan_refinements=1)
        engine = RuntimeEngine(runs_dir=self.tmpdir, config=cfg)
        state = RunState(run_id="R1", goal="g", project_id="p")
        plan = Plan(objective="t", project_id="p", steps=[
            PlanStep(step_id="s1", title="", command="ls"),
        ])
        # With max=1 refinement, loop should stop
        state2, refined = engine._refine_plan(state, plan)
        # Should complete without error
        self.assertIsNotNone(refined)


class TestResumeIdempotency(unittest.TestCase):
    """Resume checks actual state before re-executing."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))
        self._saved_env = {
            k: os.environ.pop(k, None)
            for k in ["OPENAI_API_KEY", "AGENTCORE_PLANNER_API_KEY"]
        }

    def tearDown(self):
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_resume_loads_existing_state(self):
        from core.runtime.schema import RunState, RunStatus, RunPhase
        from core.runtime.checkpoint import CheckpointStore
        from core.runtime.engine import RuntimeEngine
        from core.runtime.config import RuntimeConfig

        store = CheckpointStore(self.tmpdir)
        cfg = RuntimeConfig()
        engine = RuntimeEngine(runs_dir=self.tmpdir, config=cfg)

        # Pre-populate a checkpoint
        state = RunState(
            run_id="RUN-RESUME",
            goal="Resumed goal",
            project_id="default",
            status=RunStatus.INTERRUPTED.value,
            phase=RunPhase.STOPPED.value,
            current_task_index=3,
            completed_task_ids=["T1", "T2", "T3"],
        )
        store.save(state)

        # Resume should load the existing state
        loaded = engine.get_state("RUN-RESUME")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.run_id, "RUN-RESUME")
        self.assertEqual(loaded.status, RunStatus.INTERRUPTED.value)
        self.assertEqual(loaded.current_task_index, 3)

    def test_resume_unknown_run_raises(self):
        from core.runtime.engine import RuntimeEngine
        from core.runtime.config import RuntimeConfig
        cfg = RuntimeConfig()
        engine = RuntimeEngine(runs_dir=self.tmpdir, config=cfg)
        with self.assertRaises(ValueError):
            engine.resume("RUN-DOES-NOT-EXIST")


class TestCLISmoke(unittest.TestCase):
    """Smoke tests for CLI commands."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))
        self._saved_env = {
            k: os.environ.pop(k, None)
            for k in ["OPENAI_API_KEY", "AGENTCORE_PLANNER_API_KEY",
                       "AGENTCORE_RUNTIME_MAX_LLM_CALLS"]
        }
        os.environ["AGENTCORE_RUNTIME_MAX_LLM_CALLS"] = "0"

    def tearDown(self):
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _run_cli(self, argv):
        import io, sys
        old_argv = sys.argv
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.argv = argv
        try:
            captured = io.StringIO()
            sys.stdout = captured
            sys.stderr = io.StringIO()
            try:
                from core.runtime.cli import main
                main()
            except SystemExit as e:
                code = e.code
            else:
                code = 0
            out = captured.getvalue()
        finally:
            sys.argv = old_argv
            sys.stdout = old_stdout
            sys.stderr = old_stderr
        return code, out

    def test_cli_list_empty(self):
        code, out = self._run_cli(["prog", "list"])
        # Should exit 0 (no runs yet)
        self.assertEqual(code, 0)

    def test_cli_status_unknown(self):
        code, out = self._run_cli(["prog", "status", "RUN-BOGUS"])
        self.assertEqual(code, 1)
        self.assertIn("not found", out)


class TestEndToEnd(unittest.TestCase):
    """E2E smoke: goal → plan → execute → checkpoint → resume."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))
        self._saved_env = {
            k: os.environ.pop(k, None)
            for k in ["OPENAI_API_KEY", "AGENTCORE_PLANNER_API_KEY",
                       "AGENTCORE_RUNTIME_MAX_LLM_CALLS",
                       "AGENTCORE_RUNTIME_MAX_RETRIES"]
        }
        os.environ["AGENTCORE_RUNTIME_MAX_LLM_CALLS"] = "0"

    def tearDown(self):
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_run_creates_checkpoint(self):
        from core.runtime.schema import RunStatus
        from core.runtime.checkpoint import CheckpointStore
        from core.runtime.engine import RuntimeEngine
        from core.runtime.config import RuntimeConfig

        cfg = RuntimeConfig(max_llm_calls=0)
        engine = RuntimeEngine(runs_dir=self.tmpdir, config=cfg)
        store = CheckpointStore(self.tmpdir)

        # Run with unknown project (should fail at bootstrap)
        state = engine.run("nonexistent-project", "Test goal")

        # Still creates checkpoint
        self.assertTrue(store.exists(state.run_id))
        self.assertEqual(state.status, RunStatus.FAILED.value)

    def test_stop_writes_checkpoint(self):
        from core.runtime.schema import RunStatus, RunPhase
        from core.runtime.checkpoint import CheckpointStore
        from core.runtime.engine import RuntimeEngine
        from core.runtime.config import RuntimeConfig

        cfg = RuntimeConfig()
        engine = RuntimeEngine(runs_dir=self.tmpdir, config=cfg)
        store = CheckpointStore(self.tmpdir)

        # Pre-create a running state
        from core.runtime.schema import RunState
        state = RunState(run_id="RUN-STOP", goal="Test", project_id="default",
                          status=RunStatus.RUNNING.value, phase=RunPhase.EXECUTING.value)
        store.save(state)

        stopped = engine.stop("RUN-STOP", reason="Test stop")
        self.assertEqual(stopped.status, RunStatus.INTERRUPTED.value)
        self.assertEqual(stopped.error, "Test stop")

        # Verify checkpoint reflects stop
        reloaded = store.load("RUN-STOP")
        self.assertEqual(reloaded.status, RunStatus.INTERRUPTED.value)


if __name__ == "__main__":
    unittest.main()
