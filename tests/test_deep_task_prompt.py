"""tests/test_deep_task_prompt.py
Targeted tests for DeepTaskPrompt (core/tasks/schema.py).

Covers all 12 quality requirements:
  1. valid primitive creation
  2. required-field validation
  3. serialization/deserialization round-trip
  4. deterministic representation
  5. acceptance criteria
  6. verification requirements
  7. failure protocol
  8. evidence requirements
  9. learning-capture structure
 10. expected_outcome
11. malformed input rejection
12. compatibility with existing Agent Core abstractions
"""

from __future__ import annotations

import json
import unittest

from core.tasks.schema import (
    DeepTaskPrompt,
    DTP_EVIDENCE_TYPES,
    new_dtp_id,
    TaskStatus,
    Task,
    TaskStep,
    StepType,
)


# ── Fixtures ───────────────────────────────────────────────────────────────

MINIMAL_VALID = dict(
    prompt_id="DTP-00001",
    task_id="TASK-0001",
    intent="Fix enum value attribute error in adapter",
    goal="adapter.py emits events correctly when state fields are str",
    expected_evidence_types=["COMMAND_RESULT"],
    acceptance_criteria=["pytest tests/test_console.py passes"],
)

FULL_VALID = dict(
    prompt_id="DTP-00001",
    task_id="TASK-0001",
    project_id="agent-core",
    intent="Add SSE real-time push to Live Console",
    goal="Console SSE pushes events on publish, not polling",
    context=["core/console/api.py", "core/events/bus.py"],
    prerequisites=["Live Console runs on port 8090"],
    scope=["core/console/api.py"],
    files=["core/console/api.py"],
    must=["Use EventBus.subscribe()"],
    must_not=["Poll bus.events()", "Use time.sleep in hot path"],
    constraints=["Stdlib only", "Keep existing API"],
    strategy="Subscribe SSE clients to EventBus. Non-blocking queue per client.",
    reasoning_steps=["inspect", "reason", "modify", "test", "verify", "report"],
    acceptance_criteria=[
        "SSE receives events < 500ms after publish()",
        "healthz returns 200 during SSE",
        "2 concurrent SSE clients both receive events",
    ],
    done_when="SSE test confirms push latency < 500ms",
    verification_requirements=[
        "Run SSE smoke test",
        "Verify 2 clients receive same events",
        "Verify healthz not blocked",
    ],
    verify_with=["curl SSE test", "concurrent client test"],
    expected_evidence_types=["COMMAND_RESULT", "TEST", "FILE_STATE"],
    failure_protocol="Retry up to 3 times. If retry fails, emit REPLAN request.",
    failure_actions=["inspect", "test", "retry", "replan"],
    max_retries=3,
    recovery_strategy="Reduce scope to single SSE client first",
    required_evidence=["test output", "git diff"],
    evidence_after_success=["pytest output", "git diff", "commit hash"],
    evidence_after_failure=["pytest output", "error trace", "git status"],
    observations=["EventBus.publish is synchronous"],
    decisions=["Use queue per SSE client to avoid blocking"],
    actions_taken=["Added bus.subscribe in SSEClient.__init__"],
    failure_reason="",
    recovery_applied="",
    lesson="",
    reusable_pattern="",
    evaluation_id="",
    expected_outcome="SSE clients receive events within 500ms of publish",
    expected_changed_files=["core/console/api.py"],
    expected_verification="2 SSE clients receive all events, healthz=200",
)


class TestDeepTaskPromptCreation(unittest.TestCase):
    """1. valid primitive creation."""

    def test_minimal_valid(self):
        dtp = DeepTaskPrompt(**MINIMAL_VALID)
        self.assertEqual(dtp.prompt_id, "DTP-00001")
        self.assertEqual(dtp.intent, MINIMAL_VALID["intent"])

    def test_full_valid(self):
        dtp = DeepTaskPrompt(**FULL_VALID)
        self.assertEqual(dtp.project_id, "agent-core")
        self.assertIn("Subscribe SSE clients", dtp.strategy)

    def test_defaults(self):
        dtp = DeepTaskPrompt(prompt_id="DTP-00002", task_id="TASK-0002",
                             intent="test", goal="test",
                             expected_evidence_types=["TEST"])
        self.assertEqual(dtp.max_retries, 3)
        self.assertEqual(dtp.created_by, "gpt-director")
        self.assertEqual(dtp.schema_version, 1)


class TestDeepTaskPromptValidation(unittest.TestCase):
    """2. required-field validation + 11. malformed input rejection."""

    def test_missing_prompt_id(self):
        # prompt_id is required (no default); omit it → TypeError
        with self.assertRaises(TypeError):
            DeepTaskPrompt(task_id="TASK-0001",
                           intent="test", goal="test",
                           expected_evidence_types=["TEST"])

    def test_missing_task_id(self):
        # task_id is required (no default); omit it → TypeError
        with self.assertRaises(TypeError):
            DeepTaskPrompt(prompt_id="DTP-00001",
                           intent="test", goal="test",
                           expected_evidence_types=["TEST"])

    def test_missing_intent(self):
        d = dict(MINIMAL_VALID)
        del d["intent"]
        dtp = DeepTaskPrompt(**d)
        ok, reason = dtp.validate()
        self.assertFalse(ok)
        self.assertIn("intent", reason)

    def test_missing_goal(self):
        d = dict(MINIMAL_VALID)
        del d["goal"]
        dtp = DeepTaskPrompt(**d)
        ok, reason = dtp.validate()
        self.assertFalse(ok)
        self.assertIn("goal", reason)

    def test_missing_acceptance_and_done_when(self):
        d = dict(MINIMAL_VALID)
        del d["acceptance_criteria"]
        dtp = DeepTaskPrompt(**d)
        ok, reason = dtp.validate()
        self.assertFalse(ok)
        self.assertIn("acceptance_criteria", reason.lower())

    def test_missing_expected_evidence_types(self):
        d = dict(MINIMAL_VALID)
        del d["expected_evidence_types"]
        dtp = DeepTaskPrompt(**d)
        ok, reason = dtp.validate()
        self.assertFalse(ok)
        self.assertIn("expected_evidence_types", reason)

    def test_invalid_evidence_type(self):
        d = dict(MINIMAL_VALID)
        d["expected_evidence_types"] = ["NOT_A_TYPE"]
        dtp = DeepTaskPrompt(**d)
        ok, reason = dtp.validate()
        self.assertFalse(ok)
        self.assertIn("Unknown evidence type", reason)

    def test_invalid_failure_action(self):
        d = dict(MINIMAL_VALID)
        d["failure_actions"] = ["invalid_action"]
        dtp = DeepTaskPrompt(**d)
        ok, reason = dtp.validate()
        self.assertFalse(ok)
        self.assertIn("failure_action", reason)

    def test_negative_max_retries(self):
        d = dict(MINIMAL_VALID)
        d["max_retries"] = -1
        dtp = DeepTaskPrompt(**d)
        ok, reason = dtp.validate()
        self.assertFalse(ok)
        self.assertIn("max_retries", reason)

    def test_valid_with_done_when_instead_of_acceptance(self):
        d = dict(MINIMAL_VALID)
        del d["acceptance_criteria"]
        d["done_when"] = "tests pass"
        dtp = DeepTaskPrompt(**d)
        ok, reason = dtp.validate()
        self.assertTrue(ok)

    def test_is_valid_helper(self):
        dtp = DeepTaskPrompt(**MINIMAL_VALID)
        self.assertTrue(dtp.is_valid())
        bad = DeepTaskPrompt(prompt_id="", task_id="", intent="", goal="",
                            expected_evidence_types=[])
        self.assertFalse(bad.is_valid())


class TestDeepTaskPromptSerialization(unittest.TestCase):
    """3. serialization/deserialization round-trip."""

    def test_to_dict_full(self):
        dtp = DeepTaskPrompt(**FULL_VALID)
        d = dtp.to_dict()
        self.assertEqual(d["prompt_id"], "DTP-00001")
        self.assertEqual(d["intent"], FULL_VALID["intent"])
        self.assertIsInstance(d["reasoning_steps"], list)

    def test_from_dict_full(self):
        dtp = DeepTaskPrompt(**FULL_VALID)
        d = dtp.to_dict()
        restored = DeepTaskPrompt.from_dict(d)
        self.assertEqual(restored.prompt_id, dtp.prompt_id)
        self.assertEqual(restored.intent, dtp.intent)
        self.assertEqual(restored.strategy, dtp.strategy)
        self.assertEqual(restored.max_retries, 3)
        self.assertEqual(restored.reasoning_steps, FULL_VALID["reasoning_steps"])

    def test_to_json_roundtrip(self):
        dtp = DeepTaskPrompt(**FULL_VALID)
        text = dtp.to_json()
        self.assertIsInstance(text, str)
        restored = DeepTaskPrompt.from_json(text)
        self.assertEqual(restored.prompt_id, dtp.prompt_id)

    def test_minimal_roundtrip(self):
        dtp = DeepTaskPrompt(**MINIMAL_VALID)
        d = dtp.to_dict()
        restored = DeepTaskPrompt.from_dict(d)
        self.assertEqual(restored.prompt_id, dtp.prompt_id)
        self.assertTrue(restored.is_valid())


class TestDeepTaskPromptDeterministic(unittest.TestCase):
    """4. deterministic representation."""

    def test_same_input_same_output(self):
        d1 = DeepTaskPrompt(**FULL_VALID)
        d2 = DeepTaskPrompt(**FULL_VALID)
        self.assertEqual(d1.to_json(), d2.to_json())

    def test_deterministic_validation(self):
        dtp = DeepTaskPrompt(**FULL_VALID)
        r1 = dtp.validate()
        r2 = dtp.validate()
        self.assertEqual(r1, r2)

    def test_idempotent_serialization(self):
        dtp = DeepTaskPrompt(**FULL_VALID)
        j1 = dtp.to_json()
        restored = DeepTaskPrompt.from_json(j1)
        j2 = restored.to_json()
        self.assertEqual(json.loads(j1), json.loads(j2))


class TestDeepTaskPromptAcceptanceCriteria(unittest.TestCase):
    """5. acceptance criteria — must be present and validatable."""

    def test_acceptance_criteria_required_or_done_when(self):
        dtp = DeepTaskPrompt(**MINIMAL_VALID)
        self.assertTrue(len(dtp.acceptance_criteria) > 0)

    def test_acceptance_criteria_in_full(self):
        dtp = DeepTaskPrompt(**FULL_VALID)
        self.assertGreater(len(dtp.acceptance_criteria), 0)
        self.assertIn("SSE receives events < 500ms after publish()",
                      dtp.acceptance_criteria)


class TestDeepTaskPromptVerification(unittest.TestCase):
    """6. verification requirements — proof of success."""

    def test_verification_requirements_present(self):
        dtp = DeepTaskPrompt(**FULL_VALID)
        self.assertTrue(len(dtp.verification_requirements) > 0)
        self.assertIn("Run SSE smoke test", dtp.verification_requirements)

    def test_verify_with_present(self):
        dtp = DeepTaskPrompt(**FULL_VALID)
        self.assertIn("curl SSE test", dtp.verify_with)

    def test_expected_evidence_types_uses_valid_vocabulary(self):
        dtp = DeepTaskPrompt(**FULL_VALID)
        for et in dtp.expected_evidence_types:
            self.assertIn(et, DTP_EVIDENCE_TYPES)


class TestDeepTaskPromptFailureProtocol(unittest.TestCase):
    """7. failure protocol — bounded recovery."""

    def test_failure_protocol_present(self):
        dtp = DeepTaskPrompt(**FULL_VALID)
        self.assertTrue(len(dtp.failure_protocol) > 0)
        self.assertIn("retry", dtp.failure_protocol.lower())

    def test_failure_actions_validated(self):
        dtp = DeepTaskPrompt(**FULL_VALID)
        valid = {"inspect", "reason", "modify", "test", "verify",
                 "report", "retry", "replan", "stop"}
        for fa in dtp.failure_actions:
            self.assertIn(fa, valid)

    def test_max_retries_bounded(self):
        dtp = DeepTaskPrompt(**FULL_VALID)
        self.assertGreaterEqual(dtp.max_retries, 0)
        self.assertLessEqual(dtp.max_retries, 10)  # sanity bound

    def test_recovery_strategy_present(self):
        dtp = DeepTaskPrompt(**FULL_VALID)
        self.assertTrue(len(dtp.recovery_strategy) > 0)


class TestDeepTaskPromptEvidenceRequirements(unittest.TestCase):
    """8. evidence requirements."""

    def test_required_evidence_present(self):
        dtp = DeepTaskPrompt(**FULL_VALID)
        self.assertIn("test output", dtp.required_evidence)
        self.assertIn("git diff", dtp.required_evidence)

    def test_evidence_after_success(self):
        dtp = DeepTaskPrompt(**FULL_VALID)
        self.assertIn("pytest output", dtp.evidence_after_success)

    def test_evidence_after_failure(self):
        dtp = DeepTaskPrompt(**FULL_VALID)
        self.assertIn("error trace", dtp.evidence_after_failure)


class TestDeepTaskPromptLearningCapture(unittest.TestCase):
    """9. learning-capture structure — filled after execution + evaluation."""

    def test_learning_fields_present(self):
        dtp = DeepTaskPrompt(**FULL_VALID)
        self.assertTrue(hasattr(dtp, "observations"))
        self.assertTrue(hasattr(dtp, "decisions"))
        self.assertTrue(hasattr(dtp, "actions_taken"))
        self.assertTrue(hasattr(dtp, "failure_reason"))
        self.assertTrue(hasattr(dtp, "recovery_applied"))
        self.assertTrue(hasattr(dtp, "lesson"))
        self.assertTrue(hasattr(dtp, "reusable_pattern"))
        self.assertTrue(hasattr(dtp, "evaluation_id"))

    def test_learning_ready_requires_evaluation(self):
        dtp = DeepTaskPrompt(**FULL_VALID)
        # Not ready without evaluation
        self.assertFalse(dtp.learning_ready())
        # Ready when evaluation_id + lesson + pattern are set
        dtp.evaluation_id = "EVAL-00001"
        dtp.lesson = "Use queue per SSE client to avoid blocking bus"
        dtp.reusable_pattern = "Bus subscriber with non-blocking queue"
        self.assertTrue(dtp.learning_ready())

    def test_learning_fields_populated(self):
        dtp = DeepTaskPrompt(**FULL_VALID)
        self.assertEqual(dtp.observations, ["EventBus.publish is synchronous"])
        self.assertEqual(dtp.decisions, ["Use queue per SSE client to avoid blocking"])


class TestDeepTaskPromptExpectedOutcome(unittest.TestCase):
    """10. expected_outcome — explicit outcome description."""

    def test_expected_outcome_present(self):
        dtp = DeepTaskPrompt(**FULL_VALID)
        self.assertTrue(len(dtp.expected_outcome) > 0)
        self.assertIn("500ms", dtp.expected_outcome)

    def test_expected_changed_files(self):
        dtp = DeepTaskPrompt(**FULL_VALID)
        self.assertIn("core/console/api.py", dtp.expected_changed_files)

    def test_expected_verification_present(self):
        dtp = DeepTaskPrompt(**FULL_VALID)
        self.assertIn("healthz=200", dtp.expected_verification)


class TestDeepTaskPromptCompatibility(unittest.TestCase):
    """12. compatibility with existing Agent Core abstractions."""

    def test_deep_task_prompt_uses_existing_evidence_vocabulary(self):
        from core.evaluation.schema import EvidenceType
        dtp = DeepTaskPrompt(**FULL_VALID)
        for et in dtp.expected_evidence_types:
            # At minimum, TEST and COMMAND_RESULT must be in EvidenceType
            if et in ("TEST", "COMMAND_RESULT", "FILE_STATE", "ASSERTION"):
                self.assertIn(et, [e.value for e in EvidenceType])

    def test_deep_task_prompt_integrates_with_task(self):
        # A DeepTaskPrompt should be usable alongside a Task
        dtp = DeepTaskPrompt(**FULL_VALID)
        task = Task(
            task_id=dtp.task_id,
            project_id=dtp.project_id,
            title=dtp.goal,
            description=dtp.intent,
        )
        self.assertEqual(task.task_id, dtp.task_id)
        self.assertEqual(task.status, TaskStatus.PENDING)

    def test_deep_task_prompt_id_generator(self):
        id1 = new_dtp_id()
        id2 = new_dtp_id()
        self.assertTrue(id1.startswith("DTP-"))
        self.assertTrue(id2.startswith("DTP-"))
        # IDs are monotonically increasing (time-based)
        self.assertLessEqual(id1, id2)


class TestDeepTaskPromptEvidenceTypeVocabulary(unittest.TestCase):
    """Verify DTP_EVIDENCE_TYPES vocabulary is stable."""

    def test_all_types_are_strings(self):
        for et in DTP_EVIDENCE_TYPES:
            self.assertIsInstance(et, str)

    def test_all_types_uppercase(self):
        for et in DTP_EVIDENCE_TYPES:
            self.assertEqual(et, et.upper())

    def test_minimal_required_types_present(self):
        required = {"TEST", "COMMAND_RESULT", "FILE_STATE"}
        self.assertTrue(required.issubset(set(DTP_EVIDENCE_TYPES)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
