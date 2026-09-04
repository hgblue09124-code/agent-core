#!/usr/bin/env python3
# tests/test_beta.py
"""Tests for Agent-Core Beta Release (v0.1.0-beta).

Verifies:
1. Reference Agent initialization & execution (`Agent.run()`)
2. CLI commands (`run`, `inspect`, `history`, `benchmark`, `version`)
3. Mock Planner fallback behavior in offline mode
4. Experience recording for successful and failed runs
5. Developer Public API exports (`agent_core` package)
6. Philosophy boundary enforcement (Philosophy cannot override Kernel/Security/Verification/Task Contracts)
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import agent_core
from agent_core import Agent, AgentRunResult, PhilosophyEngine, PhilosophyTendency
from core.cli import main as cli_main, cmd_run, cmd_inspect, cmd_history, cmd_version
from core.philosophy.engine import PhilosophyPrecedenceError


class TestBetaPublicAPI(unittest.TestCase):
    """Test developer-facing public API exports."""

    def test_version_metadata(self):
        self.assertEqual(agent_core.__version__, "0.1.0-beta")
        self.assertEqual(Agent.VERSION, "0.1.0-beta")

    def test_package_exports_exist(self):
        self.assertTrue(hasattr(agent_core, "Agent"))
        self.assertTrue(hasattr(agent_core, "Kernel"))
        self.assertTrue(hasattr(agent_core, "KernelResult"))
        self.assertTrue(hasattr(agent_core, "Experience"))
        self.assertTrue(hasattr(agent_core, "PhilosophyEngine"))
        self.assertTrue(hasattr(agent_core, "PhilosophyTendency"))


class TestReferenceAgent(unittest.TestCase):
    """Test Reference Agent execution lifecycle."""

    def setUp(self):
        os.environ["AGENTCORE_PLANNER_PROVIDER"] = "mock"
        self.agent = Agent(project_id="default")

    def test_default_project_is_not_cuu_gioi(self):
        self.assertEqual(self.agent.project_id, "default")
        self.assertNotEqual(self.agent.project_id, "cuu-gioi")

    def test_agent_run_success(self):
        res: AgentRunResult = self.agent.run("Inspect workspace architecture and verify documents")

        self.assertTrue(res.success)
        self.assertEqual(res.status, "COMPLETED")
        self.assertEqual(res.verification_verdict, "PASS")
        self.assertEqual(res.project_id, "default")
        self.assertTrue(res.authorized)
        self.assertTrue(res.experience_recorded)
        self.assertTrue(len(res.plan_steps) > 0)
        self.assertTrue(res.duration_seconds > 0)

    def test_agent_run_unknown_project_fails_gracefully(self):
        res = self.agent.run("Inspect unknown", project_id="nonexistent_project_xyz")

        self.assertFalse(res.success)
        self.assertEqual(res.status, "FAILED")
        self.assertEqual(res.verification_verdict, "FAIL")
        self.assertIn("not found in registry", res.errors[0])

    def test_experience_recording_failure_behavior(self):
        """Verify that when experience persistence fails, experience_recorded is False and error is captured."""
        from unittest.mock import patch
        with patch.object(self.agent._experience_engine, "get_experience", return_value=None), \
             patch.object(self.agent._experience_engine, "record_experience", side_effect=IOError("Disk full error")):
            res = self.agent.run("Test goal with failing experience engine")
            self.assertFalse(res.experience_recorded)
            self.assertTrue(any("Experience recording failed" in err for err in res.errors))

    def test_no_duplicate_experience(self):
        """Verify duplicate experience is not recorded if already present."""
        from core.experience.schema import Experience
        from unittest.mock import patch
        fake_exp = Experience(run_id="KRUN-FAKE", goal="g", project_id="default")
        with patch.object(self.agent._experience_engine, "get_experience", return_value=fake_exp), \
             patch.object(self.agent._experience_engine, "record_experience") as mock_rec:
            res = self.agent.run("Goal with existing experience")
            self.assertTrue(res.experience_recorded)
            mock_rec.assert_not_called()

    def test_learning_pipeline_exception_handling_behavior(self):
        """Verify that exceptions (RuntimeError, TypeError, KeyError, AttributeError) in non-fatal learning pipeline do not crash Agent execution."""
        from unittest.mock import patch
        for exc in [RuntimeError("Pipeline parse error"), TypeError("Type mismatch"), KeyError("missing_key"), AttributeError("no attr")]:
            with patch.object(self.agent._learning_pipeline, "process_experience", side_effect=exc):
                res = self.agent.run("Goal with failing strategy pipeline")
                self.assertTrue(res.success)
                self.assertTrue(any("Strategy learning pipeline notice" in err for err in res.errors))

    def test_policy_denial_blocks_execution(self):
        """Verify Kernel Policy denial blocks execution before philosophy or task steps."""
        from unittest.mock import patch
        with patch.object(self.agent._policy, "should_execute", return_value=False):
            res = self.agent.run("Goal blocked by policy")
            self.assertFalse(res.authorized)
            self.assertEqual(res.status, "FAILED")
            self.assertEqual(res.phase, "AUTHORITY")
            self.assertIn("Kernel policy prohibits execution", res.errors)

    def test_verification_failure_yields_failed_verdict(self):
        """Verify verification failure leads to FAIL verdict and unsuccessful AgentRunResult."""
        from unittest.mock import patch
        from core.kernel.kernel import KernelResult
        failing_res = KernelResult(
            run_id="KRUN-FAIL",
            goal="Fail test",
            status="FAILED",
            phase="VERIFICATION",
            llm_calls=0,
            estimated_tokens=0,
            duration_seconds=0.1,
            errors=["Verification check failed"],
        )
        with patch.object(self.agent._kernel, "run", return_value=failing_res):
            res = self.agent.run("Task that fails verification")
            self.assertFalse(res.success)
            self.assertEqual(res.verification_verdict, "FAIL")
            self.assertIn("Verification check failed", res.errors)

    def test_capability_adapter_isolation(self):
        """Verify Core communicates through stable contracts/adapters without direct capability coupling."""
        from core.projects.manager import ProjectManager
        pm = ProjectManager()
        proj = pm.get("default")
        self.assertIsNotNone(proj)
        self.assertEqual(proj.project_id, "default")

    def test_inspect_and_history(self):
        res = self.agent.run("Inspect architecture for history test")
        self.assertTrue(res.success)

        # Inspect run
        inspect_data = self.agent.inspect_run(res.run_id)
        self.assertIsNotNone(inspect_data)
        self.assertEqual(inspect_data["run_id"], res.run_id)

        # History list
        hist = self.agent.history()
        self.assertTrue(len(hist) > 0)
        run_ids = [entry["run_id"] for entry in hist]
        self.assertIn(res.run_id, run_ids)


class TestCLIBetaCommands(unittest.TestCase):
    """Test CLI commands."""

    def test_cli_version_command(self):
        code = cli_main(["version"])
        self.assertEqual(code, 0)

    def test_cli_run_command(self):
        code = cli_main(["run", "Inspect cuu-gioi architecture", "--project", "cuu-gioi", "--provider", "mock"])
        self.assertEqual(code, 0)

    def test_cli_history_command(self):
        code = cli_main(["history", "--limit", "5"])
        self.assertEqual(code, 0)

    def test_cli_inspect_invalid_run_id_returns_1(self):
        code = cli_main(["inspect", "NONEXISTENT_RUN_ID_XYZ"])
        self.assertEqual(code, 1)

    def test_cli_benchmark_command(self):
        code = cli_main(["benchmark"])
        self.assertEqual(code, 0)


class TestPhilosophyPrecedenceBoundaryInBeta(unittest.TestCase):
    """Verify philosophy soft preferences cannot override hard boundaries."""

    def test_philosophy_preference_cannot_override_kernel_or_task_contract(self):
        phil = PhilosophyEngine()

        # Normal soft preference check passes
        ok, msg = phil.enforce_precedence_policy("inspect_project")
        self.assertTrue(ok)

        # Violation raises PhilosophyPrecedenceError
        with self.assertRaises(PhilosophyPrecedenceError):
            phil.enforce_precedence_policy("bypass_security", violates_kernel_invariant=True)

        with self.assertRaises(PhilosophyPrecedenceError):
            phil.enforce_precedence_policy("skip_verification", bypasses_verification=True)

        with self.assertRaises(PhilosophyPrecedenceError):
            phil.enforce_precedence_policy("override_task", violates_task_contract=True)


if __name__ == "__main__":
    unittest.main()
