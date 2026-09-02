#!/usr/bin/env python3
# tests/test_planner.py
"""Planner v0.2 — unit tests.

Run: python tests/test_planner.py
Or: python -m unittest tests.test_planner -v

All tests run offline. No external API calls.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.planner.schema import (
    Plan, PlanStep, VerificationCriterion, PlanComplexity,
    ValidationResult, ValidationError, is_valid_step_id,
)
from core.planner.context import (
    ContextBuilder, PlannerContext, build_context,
    estimate_tokens, estimate_tokens_words, estimate_tokens_combined,
)
from core.planner.prompt import (
    build_system_prompt, build_user_prompt, build_full_prompt,
    PromptConfig, strip_markdown_fences, parse_llm_response,
)
from core.planner.validator import (
    PlanValidator, validate_plan,
    _FORBIDDEN_COMMANDS, _FORBIDDEN_SHELL_PATTERNS,
)
from core.planner.planner import (
    Planner, MockPlannerProvider, PlanResult,
    plan_to_task, create_provider, load_provider_config,
)
from core.tasks.schema import Task, TaskStatus, StepType


# ── Schema tests ────────────────────────────────────────────────────────

class TestSchema(unittest.TestCase):
    """Tests for Plan/PlanStep/VerificationCriterion schema."""

    def test_plan_roundtrip(self):
        """Plan.to_dict → from_dict is lossless."""
        plan = Plan(
            objective="Test the system",
            project_id="proj-x",
            assumptions=["Assumption 1"],
            steps=[
                PlanStep(
                    step_id="step-1",
                    title="Inspect",
                    description="Do an inspect",
                    step_type="inspect",
                    dependencies=[],
                    command="",
                    arguments=[],
                    expected_result="metadata",
                    verify_contains=[],
                    verify_not_contains=[],
                    expect_exit_code=0,
                ),
                PlanStep(
                    step_id="step-2",
                    title="Run echo",
                    step_type="shell",
                    dependencies=["step-1"],
                    command="echo",
                    arguments=["hello"],
                    verify_contains=["hello"],
                    expect_exit_code=0,
                ),
            ],
            verification=[
                VerificationCriterion(
                    description="Echo output contains hello",
                    method="manual",
                    command="",
                    args=[],
                    expect_exit_code=0,
                    verify_contains=["hello"],
                ),
            ],
            risks=["Minor"],
            estimated_complexity=PlanComplexity.SIMPLE,
            notes="Test note",
        )
        d = plan.to_dict()
        restored = Plan.from_dict(d)
        self.assertEqual(restored.objective, "Test the system")
        self.assertEqual(len(restored.steps), 2)
        self.assertEqual(restored.steps[1].dependencies, ["step-1"])
        self.assertEqual(len(restored.verification), 1)
        self.assertEqual(restored.estimated_complexity, PlanComplexity.SIMPLE)

    def test_plan_to_json_roundtrip(self):
        """Plan.to_json → from_json is lossless."""
        plan = Plan(
            objective="JSON roundtrip",
            project_id="proj-y",
            steps=[
                PlanStep(step_id="s1", title="Step 1", step_type="inspect"),
            ],
            estimated_complexity=PlanComplexity.TRIVIAL,
        )
        j = plan.to_json()
        self.assertIsInstance(json.loads(j), dict)
        restored = Plan.from_json(j)
        self.assertEqual(restored.objective, "JSON roundtrip")

    def test_plan_summary(self):
        """Plan.summary() returns a string."""
        plan = Plan(
            objective="A test plan",
            project_id="proj-z",
            steps=[
                PlanStep(step_id="a", title="A", step_type="shell"),
                PlanStep(step_id="b", title="B", step_type="shell"),
            ],
            estimated_complexity=PlanComplexity.MODERATE,
        )
        s = plan.summary()
        self.assertIn("proj-z", s)
        self.assertIn("2 steps", s)

    def test_is_valid_step_id(self):
        """Step IDs with valid and invalid characters."""
        self.assertTrue(is_valid_step_id("step-1"))
        self.assertTrue(is_valid_step_id("STEP_2"))
        self.assertTrue(is_valid_step_id("a"))
        self.assertTrue(is_valid_step_id("inspect-files"))
        self.assertFalse(is_valid_step_id(""))         # empty
        self.assertFalse(is_valid_step_id("step 1"))   # space
        self.assertFalse(is_valid_step_id("step.1"))   # dot
        self.assertFalse(is_valid_step_id("step/1"))   # slash

    def test_verification_criterion_roundtrip(self):
        """VerificationCriterion roundtrips correctly."""
        vc = VerificationCriterion(
            description="Check output",
            method="test",
            command="pytest",
            args=["tests/"],
            expect_exit_code=0,
            verify_contains=["OK"],
        )
        d = vc.to_dict()
        restored = VerificationCriterion.from_dict(d)
        self.assertEqual(restored.method, "test")
        self.assertEqual(restored.verify_contains, ["OK"])


# ── Context builder tests ────────────────────────────────────────────────

class TestContextBuilder(unittest.TestCase):
    """Tests for context building and token estimation."""

    def test_estimate_tokens(self):
        """Token estimate is positive and proportional to text length."""
        short = "hello world"
        long_text = short * 100
        self.assertGreater(estimate_tokens(long_text), estimate_tokens(short))
        self.assertGreater(estimate_tokens(short), 0)

    def test_estimate_tokens_combined(self):
        """Combined estimator is stable."""
        t1 = estimate_tokens_combined("a")
        t2 = estimate_tokens_combined("a" * 100)
        self.assertGreater(t2, t1)

    def test_context_builder_respects_budget(self):
        """Documents exceeding budget are skipped."""
        # max_tokens=4000 → max_chars ≈ 16000
        cb = ContextBuilder(max_tokens=4000)
        cb.add_document("small", "role", "/p", "hello")
        cb.add_document("huge", "role2", "/p2", "x" * 100_000)
        # huge should be skipped
        self.assertEqual(len(cb.documents), 1)
        self.assertEqual(cb.documents[0].name, "small")

    def test_context_builder_build(self):
        """build() returns a PlannerContext."""
        cb = ContextBuilder()
        cb.add_document("AGENT.md", "agent_contract", "/p/AGENT.md", "# Contract")
        ctx = cb.build()
        self.assertIsInstance(ctx, PlannerContext)
        self.assertGreater(len(ctx.prompt_text), 0)
        self.assertGreater(ctx.stats.total_chars, 0)
        self.assertIsInstance(ctx.stats.approx_tokens, int)

    def test_build_context_from_project_docs(self):
        """build_context() assembles from three documents."""
        ctx = build_context(
            agent_contract="# AI Contract",
            architecture="# Arch",
            source_of_truth="# Truth",
            project_metadata={"project_id": "test", "name": "Test", "root_path": "/tmp", "status": "active"},
            max_tokens=4000,
        )
        self.assertIsInstance(ctx, PlannerContext)
        self.assertIn("AGENT.md", ctx.stats.documents_included)
        self.assertIn("ARCHITECTURE.md", ctx.stats.documents_included)
        self.assertIn("source-of-truth.md", ctx.stats.documents_included)

    def test_build_context_none_docs_handled(self):
        """build_context() handles None documents gracefully."""
        ctx = build_context(
            agent_contract=None,
            architecture=None,
            source_of_truth=None,
            project_metadata={"project_id": "x", "name": "X", "root_path": "/tmp", "status": "active"},
            max_tokens=4000,
        )
        self.assertIsInstance(ctx, PlannerContext)
        self.assertEqual(len(ctx.documents), 1)  # only metadata

    def test_context_stats_summary(self):
        """ContextStats.summary() is a string."""
        cb = ContextBuilder()
        cb.add_document("doc1", "role1", "/p", "content")
        ctx = cb.build()
        s = ctx.stats.summary()
        self.assertIn("chars=", s)
        self.assertIn("tokens≈", s)


# ── Prompt builder tests ────────────────────────────────────────────────

class TestPromptBuilder(unittest.TestCase):
    """Tests for deterministic prompt construction."""

    def test_system_prompt_exists(self):
        """System prompt is non-empty."""
        p = build_system_prompt()
        self.assertGreater(len(p), 0)
        self.assertIn("PLANNING", p)

    def test_user_prompt_includes_objective(self):
        """User prompt contains the objective."""
        config = PromptConfig(
            project_id="proj-x",
            project_name="Project X",
            objective="Inspect the codebase",
        )
        # Pass project name in context to test it's included
        ctx = "Project: Project X\nRoot: /root/proj-x\nStatus: active"
        _, user = build_full_prompt(config, ctx)
        self.assertIn("Inspect the codebase", user)
        self.assertIn("Project X", user)  # from context
        self.assertIn("## Required Output Schema", user)

    def test_full_prompt_returns_tuple(self):
        """build_full_prompt returns (system, user)."""
        config = PromptConfig(project_id="x", project_name="X", objective="Do X")
        system, user = build_full_prompt(config, "context")
        self.assertIsInstance(system, str)
        self.assertIsInstance(user, str)
        self.assertGreater(len(system), 0)
        self.assertGreater(len(user), 0)

    def test_strip_markdown_fences(self):
        """```json ... ``` fences are stripped."""
        raw = '```json\n{"key": "value"}\n```'
        self.assertEqual(strip_markdown_fences(raw), '{"key": "value"}')

    def test_parse_llm_response(self):
        """Valid JSON is parsed successfully."""
        raw = '{"objective": "test", "assumptions": [], "steps": [], "verification": [], "risks": [], "estimated_complexity": "simple", "notes": ""}'
        d = parse_llm_response(raw)
        self.assertEqual(d["objective"], "test")

    def test_parse_llm_response_with_fences(self):
        """JSON with markdown fences is parsed correctly."""
        raw = '```json\n{"objective": "fenced"}\n```'
        d = parse_llm_response(raw)
        self.assertEqual(d["objective"], "fenced")

    def test_parse_llm_response_invalid_raises(self):
        """Invalid JSON raises ValueError."""
        with self.assertRaises(ValueError):
            parse_llm_response("not json at all")


# ── Validation tests ────────────────────────────────────────────────────

class TestValidator(unittest.TestCase):
    """Tests for PlanValidator."""

    def _valid_plan(self) -> Plan:
        return Plan(
            objective="Inspect the project",
            project_id="cuu-gioi",
            steps=[
                PlanStep(step_id="s1", title="Inspect", step_type="inspect", dependencies=[]),
                PlanStep(step_id="s2", title="List files", step_type="shell",
                         command="ls", arguments=[], dependencies=["s1"]),
            ],
            verification=[
                VerificationCriterion(description="Check output", method="manual"),
            ],
            estimated_complexity=PlanComplexity.SIMPLE,
        )

    def test_valid_plan_passes(self):
        """A valid plan passes validation."""
        plan = self._valid_plan()
        validator = PlanValidator(project_ids={"cuu-gioi"})
        result = validator.validate(plan)
        self.assertTrue(result.valid)
        self.assertEqual(len(result.errors), 0)

    def test_empty_objective_fails(self):
        """Missing objective fails."""
        plan = self._valid_plan()
        plan.objective = ""
        validator = PlanValidator(project_ids={"cuu-gioi"})
        result = validator.validate(plan)
        self.assertFalse(result.valid)
        codes = [e.code for e in result.errors]
        self.assertIn("EMPTY_OBJECTIVE", codes)

    def test_unknown_project_id_fails(self):
        """Project ID not in registry fails."""
        plan = self._valid_plan()
        plan.project_id = "nonexistent"
        validator = PlanValidator(project_ids={"cuu-gioi"})
        result = validator.validate(plan)
        self.assertFalse(result.valid)
        codes = [e.code for e in result.errors]
        self.assertIn("INVALID_PROJECT_ID", codes)

    def test_missing_step_id_fails(self):
        """Step without step_id fails."""
        plan = self._valid_plan()
        plan.steps.append(PlanStep(step_id="", title="Bad", step_type="inspect"))
        validator = PlanValidator(project_ids={"cuu-gioi"})
        result = validator.validate(plan)
        self.assertFalse(result.valid)
        codes = [e.code for e in result.errors]
        self.assertIn("MISSING_STEP_ID", codes)

    def test_duplicate_step_id_fails(self):
        """Duplicate step_id fails."""
        plan = self._valid_plan()
        plan.steps.append(PlanStep(step_id="s1", title="Dup", step_type="inspect"))
        validator = PlanValidator(project_ids={"cuu-gioi"})
        result = validator.validate(plan)
        self.assertFalse(result.valid)
        codes = [e.code for e in result.errors]
        self.assertIn("DUPLICATE_STEP_ID", codes)

    def test_invalid_step_type_fails(self):
        """Invalid step_type fails."""
        plan = self._valid_plan()
        plan.steps.append(PlanStep(step_id="bad-type", title="Bad", step_type="run"))
        validator = PlanValidator(project_ids={"cuu-gioi"})
        result = validator.validate(plan)
        self.assertFalse(result.valid)
        codes = [e.code for e in result.errors]
        self.assertIn("INVALID_STEP_TYPE", codes)

    def test_unknown_dependency_fails(self):
        """Dependency on unknown step_id fails."""
        plan = self._valid_plan()
        plan.steps.append(PlanStep(step_id="dep-test", title="Test",
                                    step_type="inspect", dependencies=["nonexistent-step"]))
        validator = PlanValidator(project_ids={"cuu-gioi"})
        result = validator.validate(plan)
        self.assertFalse(result.valid)
        codes = [e.code for e in result.errors]
        self.assertIn("UNKNOWN_DEPENDENCY", codes)

    def test_self_dependency_fails(self):
        """Step depending on itself fails."""
        plan = self._valid_plan()
        plan.steps[0].dependencies = ["s1"]
        validator = PlanValidator(project_ids={"cuu-gioi"})
        result = validator.validate(plan)
        self.assertFalse(result.valid)
        codes = [e.code for e in result.errors]
        self.assertIn("SELF_DEPENDENCY", codes)

    def test_cyclic_dependencies_fails(self):
        """Cyclic dependencies fail."""
        plan = self._valid_plan()
        # s1 → s2 → s1
        plan.steps[0].dependencies = ["s2"]
        validator = PlanValidator(project_ids={"cuu-gioi"})
        result = validator.validate(plan)
        self.assertFalse(result.valid)
        codes = [e.code for e in result.errors]
        self.assertIn("CYCLIC_DEPENDENCIES", codes)

    def test_forbidden_command_rejected(self):
        """Steps using forbidden commands fail."""
        plan = self._valid_plan()
        plan.steps.append(PlanStep(step_id="rm-all", title="Dangerous",
                                    step_type="shell", command="rm", arguments=["-rf", "/"]))
        validator = PlanValidator(project_ids={"cuu-gioi"})
        result = validator.validate(plan)
        self.assertFalse(result.valid)
        codes = [e.code for e in result.errors]
        self.assertIn("FORBIDDEN_COMMAND", codes)

    def test_shell_injection_rejected(self):
        """Steps with shell injection patterns fail."""
        plan = self._valid_plan()
        plan.steps.append(PlanStep(step_id="inject", title="Inject",
                                    step_type="shell", command="echo",
                                    arguments=["hello; rm -rf /"]))
        validator = PlanValidator(project_ids={"cuu-gioi"})
        result = validator.validate(plan)
        self.assertFalse(result.valid)
        codes = [e.code for e in result.errors]
        self.assertIn("UNSAFE_SHELL_PATTERN", codes)

    def test_eval_pattern_rejected(self):
        """Steps with eval() are rejected."""
        plan = self._valid_plan()
        plan.steps.append(PlanStep(step_id="eval-bad", title="Eval",
                                    step_type="python", command="eval('x=1')"))
        validator = PlanValidator(project_ids={"cuu-gioi"})
        result = validator.validate(plan)
        self.assertFalse(result.valid)
        codes = [e.code for e in result.errors]
        self.assertIn("UNSAFE_PYTHON_PATTERN", codes)

    def test_no_steps_fails(self):
        """Plan with no steps fails."""
        plan = self._valid_plan()
        plan.steps = []
        validator = PlanValidator(project_ids={"cuu-gioi"})
        result = validator.validate(plan)
        self.assertFalse(result.valid)
        codes = [e.code for e in result.errors]
        self.assertIn("NO_STEPS", codes)

    def test_missing_shell_command_fails(self):
        """Shell step without command fails."""
        plan = self._valid_plan()
        plan.steps.append(PlanStep(step_id="no-cmd", title="No Command",
                                    step_type="shell", command=""))
        validator = PlanValidator(project_ids={"cuu-gioi"})
        result = validator.validate(plan)
        self.assertFalse(result.valid)
        codes = [e.code for e in result.errors]
        self.assertIn("MISSING_COMMAND", codes)

    def test_warnings_collected(self):
        """Warnings do not make validation invalid."""
        plan = self._valid_plan()
        # Force a warning by leaving the verification empty (already removed)
        # and then re-add: removing verification gives a warning
        plan.verification = []
        validator = PlanValidator(project_ids={"cuu-gioi"})
        result = validator.validate(plan)
        self.assertTrue(result.valid)
        self.assertGreater(len(result.warnings), 0)
        codes = [w.code for w in result.warnings]
        self.assertIn("NO_VERIFICATION_CRITERIA", codes)

    def test_validate_plan_convenience_function(self):
        """validate_plan() works as a one-shot function."""
        plan = self._valid_plan()
        result = validate_plan(plan, {"cuu-gioi"})
        self.assertTrue(result.valid)


# ── Mock provider tests ──────────────────────────────────────────────────

class TestMockProvider(unittest.TestCase):
    """Tests for MockPlannerProvider."""

    def test_mock_generates_valid_json(self):
        """Mock provider returns valid JSON."""
        provider = MockPlannerProvider()
        output = provider.generate("system", "user prompt")
        self.assertIsInstance(output, str)
        d = json.loads(output)
        self.assertIn("objective", d)
        self.assertIn("steps", d)

    def test_mock_call_count(self):
        """Call count increments."""
        provider = MockPlannerProvider()
        self.assertEqual(provider.call_count, 0)
        provider.generate("s", "u")
        self.assertEqual(provider.call_count, 1)

    def test_mock_response_override(self):
        """response_override returns exactly that string."""
        override = '{"objective": "override test"}'
        provider = MockPlannerProvider(response_override=override)
        self.assertEqual(provider.generate("s", "u"), override)

    def test_mock_error_on_call(self):
        """error_on_call raises RuntimeError."""
        provider = MockPlannerProvider(error_on_call=True)
        with self.assertRaises(RuntimeError):
            provider.generate("s", "u")


# ── Planner tests ──────────────────────────────────────────────────────

class TestPlanner(unittest.TestCase):
    """Tests for the Planner class."""

    def test_planner_with_mock_provider(self):
        """Planner with MockPlannerProvider returns a valid plan."""
        provider = MockPlannerProvider()
        planner = Planner(provider=provider)
        result = planner.plan("cuu-gioi", "Inspect the project structure")
        self.assertTrue(result.validation.valid)
        self.assertIsNotNone(result.plan)
        self.assertEqual(result.plan.project_id, "cuu-gioi")
        self.assertIsNotNone(result.context_stats)

    def test_planner_unknown_project(self):
        """Planner with unknown project returns error."""
        planner = Planner(provider=MockPlannerProvider())
        result = planner.plan("does-not-exist", "Do something")
        self.assertIsNone(result.plan)
        self.assertIsNotNone(result.error)
        self.assertIn("not found", result.error)

    def test_planner_invalid_llm_output(self):
        """Planner handles non-JSON LLM output."""
        provider = MockPlannerProvider(response_override="this is not json")
        planner = Planner(provider=provider)
        result = planner.plan("cuu-gioi", "Test")
        self.assertIsNone(result.plan)
        self.assertFalse(result.validation.valid)
        self.assertIn("PARSE_ERROR", [e.code for e in result.validation.errors])

    def test_planner_malformed_json_plan(self):
        """Planner handles plan missing required fields."""
        provider = MockPlannerProvider(response_override='{"objective": "ok"}')
        planner = Planner(provider=provider)
        result = planner.plan("cuu-gioi", "Test")
        self.assertIsNone(result.plan)
        self.assertFalse(result.validation.valid)

    def test_planner_context_stats(self):
        """Planner includes context statistics in result."""
        planner = Planner(provider=MockPlannerProvider())
        result = planner.plan("cuu-gioi", "Test")
        self.assertIsNotNone(result.context_stats)
        self.assertIsInstance(result.context_stats.approx_tokens, int)
        self.assertGreater(result.context_stats.total_chars, 0)

    def test_planner_provider_name(self):
        """Result includes provider name."""
        planner = Planner(provider=MockPlannerProvider())
        result = planner.plan("cuu-gioi", "Test")
        self.assertEqual(result.provider_name, "MockPlannerProvider")

    def test_create_provider_mock(self):
        """create_provider returns MockPlannerProvider by default."""
        provider = create_provider()
        self.assertIsInstance(provider, MockPlannerProvider)

    def test_load_provider_config_defaults(self):
        """load_provider_config returns defaults without env vars."""
        cfg = load_provider_config()
        self.assertEqual(cfg.provider, "mock")


# ── Plan → Task conversion tests ────────────────────────────────────────

class TestPlanToTask(unittest.TestCase):
    """Tests for plan_to_task()."""

    def _valid_plan(self) -> Plan:
        return Plan(
            objective="Inspect and list",
            project_id="cuu-gioi",
            steps=[
                PlanStep(step_id="s1", title="Inspect", step_type="inspect",
                         command="", arguments=[], dependencies=[]),
                PlanStep(step_id="s2", title="Echo hello", step_type="shell",
                         command="echo", arguments=["hello"],
                         dependencies=["s1"], verify_contains=["hello"],
                         expect_exit_code=0),
                PlanStep(step_id="s3", title="Run python", step_type="python",
                         command="core.projects.cli", arguments=["list"],
                         dependencies=["s1"]),
            ],
            estimated_complexity=PlanComplexity.SIMPLE,
            notes="Test plan",
        )

    def test_plan_to_task_maps_steps(self):
        """All steps map to TaskSteps."""
        plan = self._valid_plan()
        task = plan_to_task(plan)
        self.assertEqual(len(task.steps), 3)
        self.assertEqual(task.project_id, "cuu-gioi")
        self.assertEqual(task.title, "Inspect and list")

    def test_plan_to_task_step_types(self):
        """step_type maps to StepType correctly."""
        plan = self._valid_plan()
        task = plan_to_task(plan)
        self.assertEqual(task.steps[0].type, StepType.INSPECT)
        self.assertEqual(task.steps[1].type, StepType.SHELL)
        self.assertEqual(task.steps[2].type, StepType.PYTHON)

    def test_plan_to_task_verification_hints(self):
        """verify_contains and expect_exit_code map correctly."""
        plan = self._valid_plan()
        task = plan_to_task(plan)
        shell_step = task.steps[1]
        self.assertEqual(shell_step.verify_contains, ["hello"])
        self.assertEqual(shell_step.expect_exit_code, 0)

    def test_plan_to_task_status_pending(self):
        """Converted task has PENDING status."""
        task = plan_to_task(self._valid_plan())
        self.assertEqual(task.status, TaskStatus.PENDING)


# ── CLI behavior tests ──────────────────────────────────────────────────

class TestCLICLI(unittest.TestCase):
    """Smoke tests for CLI module."""

    def test_cli_module_imports(self):
        """CLI module can be imported without error."""
        from core.planner.cli import main, HELP, BANNER
        self.assertIsInstance(HELP, str)
        self.assertIsInstance(BANNER, str)
        self.assertIn("Planner", BANNER)

    def test_print_plan(self):
        """print_plan runs without error."""
        from core.planner.cli import print_plan
        plan = Plan(
            objective="Test",
            project_id="proj",
            steps=[
                PlanStep(step_id="s1", title="Step 1", step_type="shell",
                         command="echo", arguments=["hi"]),
            ],
            verification=[
                VerificationCriterion(description="Check output"),
            ],
            risks=["Minor risk"],
            estimated_complexity=PlanComplexity.TRIVIAL,
            notes="A note",
        )
        # Should not raise
        print_plan(plan)


# ── Test runner ─────────────────────────────────────────────────────────

def run_tests() -> bool:
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
