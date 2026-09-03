"""tests/test_construction.py
Focused tests for TaskConstructionContract (core/tasks/schema.py).

Covers:
  1. valid construction contract creation
  2. required-field validation
  3. serialization round-trip
  4. deterministic representation
  5. objective / scope / constraints
  6. acceptance criteria
  7. failure handling
  8. evidence requirements
  9. expected outcome
 10. malformed input rejection
 11. Task.attach_construction()
 12. backward compatibility (Task without construction)
"""

from __future__ import annotations

import json
import unittest

from core.tasks.schema import (
    Task,
    TaskConstructionContract,
    TaskStatus,
    DTP_EVIDENCE_TYPES,
)


# ── Fixtures ───────────────────────────────────────────────────────────────

MINIMAL_CONTRACT = dict(
    contract_id="TCC-00001",
    objective="Add SSE real-time push to Live Console",
    expected_evidence_types=["TEST", "COMMAND_RESULT"],
    acceptance_criteria=[
        "SSE receives events within 500ms of publish",
        "healthz returns 200 during SSE stream",
    ],
)

FULL_CONTRACT = dict(
    contract_id="TCC-00002",
    title="Fix adapter .value error",
    objective="Fix enum attribute error in adapter.py",
    rationale="Runtime fails with 'str' object has no attribute 'value'",
    context=["core/console/adapter.py", "core/runtime/schema.py"],
    prerequisites=["Live Console runs on port 8090"],
    scope=["core/console/adapter.py"],
    files_in_scope=["core/console/adapter.py"],
    files_not_in_scope=["core/console/cli.py"],
    must=["Use hasattr guard", "Keep existing adapter interface"],
    must_not=["Poll bus.events()", "Add new dependencies"],
    constraints=["Stdlib only", "No architectural change"],
    guidance="Use hasattr(value, 'value') else str(value) pattern.",
    reasoning_steps=["inspect", "reason", "modify", "test", "verify"],
    acceptance_criteria=[
        "pytest tests/test_console.py passes",
        "healthz returns 200",
        "SSE receives events",
    ],
    done_when="All targeted tests pass",
    verification_requirements=[
        "Run pytest tests/test_console.py",
        "Verify SSE smoke test",
    ],
    verify_with=["pytest", "curl SSE test"],
    expected_evidence_types=["TEST", "COMMAND_RESULT", "FILE_STATE"],
    required_evidence=["pytest output", "git diff"],
    evidence_after_success=["pytest output", "git diff", "commit hash"],
    evidence_after_failure=["pytest output", "error trace"],
    failure_protocol="Retry up to 3 times. If all retries fail, emit REPLAN request.",
    failure_actions=["inspect", "test", "retry", "replan"],
    max_retries=3,
    recovery_strategy="Reduce scope to single test first",
    expected_outcome="All tests pass, SSE events arrive within 500ms",
    expected_changed_files=["core/console/adapter.py"],
    expected_verification="pytest + SSE smoke both PASS",
)


# ── Creation ───────────────────────────────────────────────────────────────

class TestContractCreation(unittest.TestCase):
    """1. valid construction contract creation."""

    def test_minimal_contract(self):
        c = TaskConstructionContract(**MINIMAL_CONTRACT)
        self.assertEqual(c.contract_id, "TCC-00001")
        self.assertEqual(c.objective, "Add SSE real-time push to Live Console")

    def test_full_contract(self):
        c = TaskConstructionContract(**FULL_CONTRACT)
        self.assertEqual(c.title, "Fix adapter .value error")
        self.assertEqual(len(c.reasoning_steps), 5)
        self.assertEqual(c.max_retries, 3)

    def test_defaults(self):
        c = TaskConstructionContract(
            contract_id="TCC-00003",
            objective="test",
            expected_evidence_types=["TEST"],
            acceptance_criteria=["pass"],
        )
        self.assertEqual(c.max_retries, 3)
        self.assertEqual(c.authored_by, "gpt-administrator")
        self.assertEqual(c.schema_version, 1)
        self.assertEqual(c.title, "")


class TestContractValidation(unittest.TestCase):
    """2. required-field validation + 10. malformed input rejection."""

    def test_missing_objective(self):
        d = dict(MINIMAL_CONTRACT)
        del d["objective"]
        c = TaskConstructionContract(**d)
        ok, reason = c.validate()
        self.assertFalse(ok)
        self.assertIn("objective", reason)

    def test_missing_evidence_types(self):
        d = dict(MINIMAL_CONTRACT)
        del d["expected_evidence_types"]
        c = TaskConstructionContract(**d)
        ok, reason = c.validate()
        self.assertFalse(ok)
        self.assertIn("evidence_type", reason)

    def test_invalid_evidence_type(self):
        d = dict(MINIMAL_CONTRACT)
        d["expected_evidence_types"] = ["NOT_A_TYPE"]
        c = TaskConstructionContract(**d)
        ok, reason = c.validate()
        self.assertFalse(ok)
        self.assertIn("Unknown evidence type", reason)

    def test_invalid_failure_action(self):
        d = dict(MINIMAL_CONTRACT)
        d["failure_actions"] = ["unknown_action"]
        c = TaskConstructionContract(**d)
        ok, reason = c.validate()
        self.assertFalse(ok)
        self.assertIn("failure_action", reason)

    def test_negative_max_retries(self):
        d = dict(MINIMAL_CONTRACT)
        d["max_retries"] = -1
        c = TaskConstructionContract(**d)
        ok, reason = c.validate()
        self.assertFalse(ok)
        self.assertIn("max_retries", reason)

    def test_valid_with_done_when(self):
        d = dict(MINIMAL_CONTRACT)
        del d["acceptance_criteria"]
        d["done_when"] = "tests pass"
        c = TaskConstructionContract(**d)
        self.assertTrue(c.validate()[0])

    def test_invalid_contract_id(self):
        c = TaskConstructionContract(
            contract_id="BAD ID!@#",
            objective="test",
            expected_evidence_types=["TEST"],
            acceptance_criteria=["pass"],
        )
        ok, reason = c.validate()
        self.assertFalse(ok)
        self.assertIn("contract_id", reason)


class TestContractSerialization(unittest.TestCase):
    """3. serialization/deserialization round-trip."""

    def test_to_dict_full(self):
        c = TaskConstructionContract(**FULL_CONTRACT)
        d = c.to_dict()
        self.assertEqual(d["contract_id"], "TCC-00002")
        self.assertIn("reasoning_steps", d)
        self.assertIn("scope", d)

    def test_from_dict_full(self):
        c = TaskConstructionContract(**FULL_CONTRACT)
        d = c.to_dict()
        restored = TaskConstructionContract.from_dict(d)
        self.assertEqual(restored.contract_id, c.contract_id)
        self.assertEqual(restored.objective, c.objective)
        self.assertEqual(restored.max_retries, 3)
        self.assertEqual(restored.reasoning_steps, FULL_CONTRACT["reasoning_steps"])

    def test_to_json_roundtrip(self):
        c = TaskConstructionContract(**FULL_CONTRACT)
        text = c.to_json()
        restored = TaskConstructionContract.from_json(text)
        self.assertEqual(restored.contract_id, c.contract_id)

    def test_minimal_roundtrip(self):
        c = TaskConstructionContract(**MINIMAL_CONTRACT)
        restored = TaskConstructionContract.from_dict(c.to_dict())
        self.assertTrue(restored.is_valid())


class TestContractDeterministic(unittest.TestCase):
    """4. deterministic representation."""

    def test_same_input_same_output(self):
        c1 = TaskConstructionContract(**FULL_CONTRACT)
        c2 = TaskConstructionContract(**FULL_CONTRACT)
        self.assertEqual(c1.to_json(), c2.to_json())

    def test_deterministic_validation(self):
        c = TaskConstructionContract(**FULL_CONTRACT)
        r1 = c.validate()
        r2 = c.validate()
        self.assertEqual(r1, r2)


class TestContractObjectiveScope(unittest.TestCase):
    """5. objective / scope / constraints."""

    def test_objective_required(self):
        c = TaskConstructionContract(**FULL_CONTRACT)
        self.assertTrue(len(c.objective) > 0)

    def test_scope_fields(self):
        c = TaskConstructionContract(**FULL_CONTRACT)
        self.assertIn("core/console/adapter.py", c.scope)
        self.assertIn("core/console/adapter.py", c.files_in_scope)
        self.assertIn("core/console/cli.py", c.files_not_in_scope)

    def test_constraints(self):
        c = TaskConstructionContract(**FULL_CONTRACT)
        self.assertIn("Stdlib only", c.constraints)


class TestContractAcceptanceCriteria(unittest.TestCase):
    """6. acceptance criteria."""

    def test_acceptance_criteria_required(self):
        c = TaskConstructionContract(**MINIMAL_CONTRACT)
        self.assertGreater(len(c.acceptance_criteria), 0)

    def test_done_when_alternative(self):
        d = dict(MINIMAL_CONTRACT)
        del d["acceptance_criteria"]
        d["done_when"] = "all tests green"
        c = TaskConstructionContract(**d)
        self.assertTrue(c.is_valid())

    def test_guidance_field(self):
        c = TaskConstructionContract(**FULL_CONTRACT)
        self.assertTrue(len(c.guidance) > 0)


class TestContractFailureHandling(unittest.TestCase):
    """7. failure handling — bounded recovery."""

    def test_failure_protocol_present(self):
        c = TaskConstructionContract(**FULL_CONTRACT)
        self.assertIn("retry", c.failure_protocol.lower())
        self.assertIn("replan", c.failure_protocol.lower())

    def test_max_retries_bounded(self):
        c = TaskConstructionContract(**FULL_CONTRACT)
        self.assertGreaterEqual(c.max_retries, 0)
        self.assertLessEqual(c.max_retries, 10)

    def test_failure_actions_validated(self):
        c = TaskConstructionContract(**FULL_CONTRACT)
        for fa in c.failure_actions:
            self.assertIn(fa, {"inspect", "reason", "modify", "test",
                                "verify", "report", "retry", "replan", "stop"})


class TestContractEvidenceRequirements(unittest.TestCase):
    """8. evidence requirements."""

    def test_required_evidence(self):
        c = TaskConstructionContract(**FULL_CONTRACT)
        self.assertIn("pytest output", c.required_evidence)

    def test_evidence_after_success(self):
        c = TaskConstructionContract(**FULL_CONTRACT)
        self.assertIn("pytest output", c.evidence_after_success)
        self.assertIn("git diff", c.evidence_after_success)

    def test_evidence_after_failure(self):
        c = TaskConstructionContract(**FULL_CONTRACT)
        self.assertIn("pytest output", c.evidence_after_failure)


class TestContractExpectedOutcome(unittest.TestCase):
    """9. expected outcome."""

    def test_expected_outcome(self):
        c = TaskConstructionContract(**FULL_CONTRACT)
        self.assertTrue(len(c.expected_outcome) > 0)
        self.assertIn("500ms", c.expected_outcome)

    def test_expected_changed_files(self):
        c = TaskConstructionContract(**FULL_CONTRACT)
        self.assertIn("core/console/adapter.py", c.expected_changed_files)

    def test_expected_verification(self):
        c = TaskConstructionContract(**FULL_CONTRACT)
        self.assertTrue(len(c.expected_verification) > 0)


class TestTaskWithConstruction(unittest.TestCase):
    """11. Task.attach_construction() + 12. backward compatibility."""

    def test_task_without_construction(self):
        t = Task(task_id="T-1", project_id="p", title="test")
        self.assertIsNone(t.construction)
        self.assertIsNone(t.to_dict().get("construction"))
        t2 = Task.from_dict(t.to_dict())
        self.assertIsNone(t2.construction)

    def test_task_with_construction(self):
        c = TaskConstructionContract(**FULL_CONTRACT)
        t = Task(task_id="T-2", project_id="agent-core", title="test", construction=c)
        self.assertIsNotNone(t.construction)
        self.assertEqual(t.construction.contract_id, "TCC-00002")

    def test_task_serialization_roundtrip_with_construction(self):
        c = TaskConstructionContract(**FULL_CONTRACT)
        t = Task(task_id="T-3", project_id="p", title="test", construction=c)
        d = t.to_dict()
        self.assertIsNotNone(d["construction"])
        self.assertEqual(d["construction"]["contract_id"], "TCC-00002")
        t2 = Task.from_dict(d)
        self.assertIsNotNone(t2.construction)
        self.assertEqual(t2.construction.contract_id, "TCC-00002")
        self.assertEqual(t2.construction.objective, FULL_CONTRACT["objective"])

    def test_construction_summary(self):
        c = TaskConstructionContract(**FULL_CONTRACT)
        summary = c.construction_summary()
        self.assertIn("TCC-00002", summary)
        self.assertIn("objective", summary)
        self.assertIn("scope", summary)


if __name__ == "__main__":
    unittest.main()
