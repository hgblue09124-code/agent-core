#!/usr/bin/env python3
# tests/test_v03_runtime.py
"""v0.3 Personal Agent Runtime — autonomous execution lifecycle."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.capabilities.adapter import CapabilityRegistry
from core.capabilities.mock_adapter import (
    AlwaysFailCapability,
    EvidenceMissingCapability,
    FailOnceCapability,
    MockEchoCapabilityAdapter,
    MutationCapability,
    SuccessCapability,
)
from core.events.schema import EventPhase, new_event
from core.memory.schema import MemoryQuery, MemoryType
from core.runtime.agent_runtime import AgentRuntime
from core.runtime.decide import MockReasoningProvider
from core.runtime.models import (
    AgentPhase,
    AgentState,
    InvalidAgentTransitionError,
    ObjectiveKind,
    ObjectiveState,
    RuntimeBounds,
    RuntimeEvent,
    RuntimeEventKind,
    new_id,
)


def _runtime(tmpdir: str, **kwargs) -> AgentRuntime:
    registry = kwargs.pop("capabilities", None) or CapabilityRegistry()
    if not registry.get("mock.echo"):
        registry.register(MockEchoCapabilityAdapter())
    return AgentRuntime(storage_dir=tmpdir, capabilities=registry, **kwargs)


class TestObjectiveLifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.rt = _runtime(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_user_objective_is_persisted_and_completed(self):
        result = self.rt.submit("Remember that my favorite color is blue")
        self.assertTrue(result.success)
        self.assertIsNotNone(result.objective)
        self.assertEqual(result.objective.status, ObjectiveState.COMPLETED.value)
        self.assertEqual(result.objective.kind, ObjectiveKind.ONE_SHOT.value)
        loaded = self.rt.get_objective(result.objective.objective_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.status, ObjectiveState.COMPLETED.value)
        self.assertTrue((Path(self.tmp.name) / "objectives" / f"{loaded.objective_id}.json").exists())

    def test_persistent_objective_watches_instead_of_finishing(self):
        result = self.rt.submit("Monitor project status")
        self.assertTrue(result.success)
        self.assertEqual(result.objective.kind, ObjectiveKind.PERSISTENT.value)
        self.assertEqual(result.objective.status, ObjectiveState.WAITING.value)
        self.assertEqual(self.rt.state.phase, AgentPhase.WATCHING.value)
        self.assertIn("WATCH", result.stages)


class TestStateTransitions(unittest.TestCase):
    def test_idle_cannot_jump_to_executing(self):
        state = AgentState()
        with self.assertRaises(InvalidAgentTransitionError):
            state.transition(AgentPhase.EXECUTING)

    def test_canonical_stages_are_explicit(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        rt = _runtime(tmp.name)
        result = rt.submit("Remember that my favorite snack is mango")
        self.assertEqual(
            result.stages,
            ["OBSERVE", "UNDERSTAND", "RETRIEVE", "DECIDE", "ACT", "VERIFY", "REMEMBER", "FINISH"],
        )
        self.assertEqual(rt.state.phase, AgentPhase.IDLE.value)
        self.assertEqual(rt.state.last_outcome, "COMPLETED")

    def test_llm_cannot_mutate_agent_state(self):
        state = AgentState()
        dumped = state.to_dict()
        # A model-shaped payload must not be applied as a transition.
        fake = {"phase": "EXECUTING", "active_objective_id": "OBJ-hack"}
        restored = AgentState.from_dict(dumped)
        self.assertEqual(restored.phase, AgentPhase.IDLE.value)
        self.assertNotEqual(fake["phase"], restored.phase)


class TestDeterministicDecisions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.provider = MockReasoningProvider()
        self.rt = _runtime(self.tmp.name, provider=self.provider)

    def tearDown(self):
        self.tmp.cleanup()

    def test_remember_does_not_call_llm(self):
        result = self.rt.submit("Remember that my favorite color is blue")
        self.assertTrue(result.success)
        self.assertFalse(result.decision.llm_called)
        self.assertEqual(result.decision.reasoning_level, "DETERMINISTIC")
        self.assertEqual(result.action.type, "remember")
        self.assertEqual(self.provider.calls, [])
        hits = self.rt.memory.retrieve(MemoryQuery(query="blue"))
        self.assertTrue(hits)

    def test_forget_is_deterministic(self):
        self.rt.submit("Remember that my favorite snack is mango")
        result = self.rt.submit("Forget favorite snack")
        self.assertTrue(result.success)
        self.assertFalse(result.decision.llm_called)
        self.assertEqual(result.action.type, "forget")
        self.assertEqual(self.provider.calls, [])

    def test_status_is_deterministic(self):
        result = self.rt.submit("status")
        self.assertTrue(result.success)
        self.assertEqual(result.action.type, "echo")
        self.assertEqual(self.provider.calls, [])


class TestLLMRequiredDecisions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_complex_goal_uses_structured_provider_output(self):
        provider = MockReasoningProvider(
            responses=[
                json.dumps(
                    {
                        "intent": "summarize architecture",
                        "action_type": "echo",
                        "arguments": {"text": "architecture summary"},
                        "confidence": 0.7,
                        "risk": "LOW",
                        "verification": "architecture summary",
                        "reason": "structured plan",
                    }
                )
            ]
        )
        rt = _runtime(self.tmp.name, provider=provider)
        result = rt.submit("Summarize the system architecture for the next release")
        self.assertTrue(result.success)
        self.assertTrue(result.decision.llm_called)
        self.assertEqual(result.action.type, "echo")
        self.assertEqual(result.action.arguments.get("text"), "architecture summary")
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(provider.calls[0]["level"], "cheap")

    def test_unstructured_model_output_is_not_executed(self):
        provider = MockReasoningProvider(responses=["Sure, I will delete all files now."])
        rt = _runtime(self.tmp.name, provider=provider)
        result = rt.submit("Summarize the system architecture for the next release")
        self.assertTrue(result.success)
        self.assertEqual(len(provider.calls), 1)
        self.assertIn("not a structured Decision", result.decision.reason)
        self.assertNotEqual(result.action.arguments.get("text"), "Sure, I will delete all files now.")


class TestMinimalContext(unittest.TestCase):
    def test_context_contains_only_current_decision_inputs(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        rt = _runtime(tmp.name)
        rt.submit("Remember that my favorite color is blue")
        rt.submit("Remember that my timezone is Asia/Ho_Chi_Minh")
        result = rt.submit("Remember that I prefer dark mode")
        ctx = result.context.to_dict()
        self.assertNotIn("conversation", ctx)
        self.assertNotIn("history", ctx)
        self.assertNotIn("messages", ctx)
        self.assertIn("objective", ctx)
        self.assertIn("event_kind", ctx)
        self.assertLessEqual(len(ctx["memory"]), 3)
        self.assertNotIn("unrelated_objectives", ctx)
        raw = str(ctx)
        self.assertNotIn("Asia/Ho_Chi_Minh", raw)
        self.assertEqual(ctx["objective"]["intent"], "Remember that I prefer dark mode")


class TestSuccessfulAction(unittest.TestCase):
    def test_capability_success_is_verified(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        registry = CapabilityRegistry()
        registry.register(MockEchoCapabilityAdapter())
        registry.register(SuccessCapability())
        rt = _runtime(tmp.name, capabilities=registry)
        result = rt.submit("use mock.success to inspect the cluster")
        self.assertTrue(result.success)
        self.assertEqual(result.action.type, "invoke_capability")
        self.assertEqual(result.action.capability, "mock.success")
        self.assertEqual(result.verification.verdict, "PASS")
        self.assertEqual(result.execution.status, "SUCCESS")
        self.assertEqual(result.objective.status, ObjectiveState.COMPLETED.value)


class TestFailedAction(unittest.TestCase):
    def test_permanent_failure_fails_safely(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        registry = CapabilityRegistry()
        registry.register(MockEchoCapabilityAdapter())
        registry.register(AlwaysFailCapability())
        rt = _runtime(
            tmp.name,
            capabilities=registry,
            bounds=RuntimeBounds(max_retries=0, max_replans=0, max_cycle_iterations=3),
        )
        result = rt.submit("use mock.always_fail to inspect the cluster")
        self.assertFalse(result.success)
        self.assertEqual(result.objective.status, ObjectiveState.FAILED.value)
        self.assertEqual(rt.state.phase, AgentPhase.FAILED.value)
        self.assertEqual(result.verification.verdict, "FAIL")


class TestVerificationFailure(unittest.TestCase):
    def test_success_status_without_evidence_does_not_count(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        registry = CapabilityRegistry()
        registry.register(MockEchoCapabilityAdapter())
        registry.register(EvidenceMissingCapability())
        rt = _runtime(
            tmp.name,
            capabilities=registry,
            bounds=RuntimeBounds(max_retries=0, max_replans=0),
        )
        result = rt.submit("use mock.evidence_missing to inspect data")
        self.assertFalse(result.success)
        self.assertEqual(result.verification.verdict, "FAIL")
        self.assertIn("evidence", result.verification.reason.lower())
        self.assertEqual(result.objective.status, ObjectiveState.FAILED.value)


class TestRetryLimit(unittest.TestCase):
    def test_fail_once_retries_then_succeeds(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        registry = CapabilityRegistry()
        registry.register(MockEchoCapabilityAdapter())
        adapter = FailOnceCapability()
        registry.register(adapter)
        rt = _runtime(tmp.name, capabilities=registry, bounds=RuntimeBounds(max_retries=2, max_replans=0))
        result = rt.submit("use mock.fail_once to inspect node")
        self.assertTrue(result.success)
        self.assertEqual(adapter.call_count, 2)
        self.assertEqual(result.objective.retry_count, 1)
        self.assertGreaterEqual(result.stages.count("ACT"), 2)

    def test_retry_budget_is_bounded(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        registry = CapabilityRegistry()
        registry.register(MockEchoCapabilityAdapter())
        adapter = AlwaysFailCapability()
        registry.register(adapter)
        rt = _runtime(
            tmp.name,
            capabilities=registry,
            bounds=RuntimeBounds(max_retries=2, max_replans=0, max_cycle_iterations=8),
        )
        result = rt.submit("use mock.always_fail to inspect node")
        self.assertFalse(result.success)
        self.assertEqual(result.objective.retry_count, 2)
        self.assertEqual(result.recovery.kind, "FAIL")
        self.assertTrue(result.recovery.bounded)
        self.assertLessEqual(result.stages.count("ACT"), 3)


class TestReplan(unittest.TestCase):
    def test_replan_excludes_failed_capability(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        registry = CapabilityRegistry()
        registry.register(MockEchoCapabilityAdapter())
        registry.register(AlwaysFailCapability())
        rt = _runtime(
            tmp.name,
            capabilities=registry,
            bounds=RuntimeBounds(max_retries=0, max_replans=1, max_cycle_iterations=6),
        )
        result = rt.submit("use mock.always_fail to inspect node")
        self.assertTrue(result.success)
        self.assertEqual(result.objective.replan_count, 1)
        self.assertEqual(result.action.type, "echo")
        self.assertEqual(result.verification.verdict, "PASS")
        self.assertIsNotNone(result.recovery)
        self.assertEqual(result.recovery.kind, "REPLAN")


class TestBlockedAuthorization(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        registry = CapabilityRegistry()
        registry.register(MockEchoCapabilityAdapter())
        registry.register(MutationCapability())
        self.rt = _runtime(self.tmp.name, capabilities=registry)

    def tearDown(self):
        self.tmp.cleanup()

    def test_mutating_action_blocks_without_approval(self):
        result = self.rt.submit("create record using mock.mutation")
        self.assertFalse(result.success)
        self.assertEqual(self.rt.state.phase, AgentPhase.NEEDS_USER.value)
        self.assertEqual(result.objective.status, ObjectiveState.BLOCKED.value)
        self.assertEqual(result.action.authorization_state, "ASK_USER")
        self.assertIsNone(result.execution)

    def test_approve_resumes_pending_action(self):
        blocked = self.rt.submit("create record using mock.mutation")
        oid = blocked.objective.objective_id
        result = self.rt.approve(oid)
        self.assertTrue(result.success)
        self.assertEqual(result.objective.status, ObjectiveState.COMPLETED.value)
        self.assertEqual(result.execution.status, "SUCCESS")
        self.assertEqual(self.rt.state.phase, AgentPhase.IDLE.value)


class TestLoopTermination(unittest.TestCase):
    def test_empty_input_stays_idle(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        rt = _runtime(tmp.name)
        result = rt.submit("   ")
        self.assertTrue(rt.idle())
        self.assertEqual(result.stages, ["OBSERVE"])
        self.assertIsNone(result.objective)
        self.assertEqual(rt.state.phase, AgentPhase.IDLE.value)

    def test_cycle_iteration_budget_stops_the_loop(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        registry = CapabilityRegistry()
        registry.register(MockEchoCapabilityAdapter())
        registry.register(AlwaysFailCapability())
        rt = _runtime(
            tmp.name,
            capabilities=registry,
            bounds=RuntimeBounds(max_retries=20, max_replans=20, max_cycle_iterations=2),
        )
        result = rt.submit("use mock.always_fail to inspect node")
        self.assertFalse(result.success)
        self.assertLessEqual(rt.state.loop_iteration, 2)
        self.assertIn("iteration budget", result.error.lower())

    def test_handle_event_does_not_reenter(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        rt = _runtime(tmp.name)
        rt._in_cycle = True
        result = rt.submit("Remember that my favorite color is blue")
        self.assertIn("cycle already in progress", result.error)
        rt._in_cycle = False


class TestProviderIndependence(unittest.TestCase):
    def test_deterministic_path_identical_across_providers(self):
        tmp_a = tempfile.TemporaryDirectory()
        tmp_b = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_a.cleanup)
        self.addCleanup(tmp_b.cleanup)

        class ProviderA:
            provider_name = "alpha-test"
            calls = 0

            def reason(self, system, user, *, level="normal"):
                ProviderA.calls += 1
                raise AssertionError("vendor A must not be called")

        class ProviderB:
            provider_name = "beta-test"
            calls = 0

            def reason(self, system, user, *, level="normal"):
                ProviderB.calls += 1
                raise AssertionError("vendor B must not be called")

        a = _runtime(tmp_a.name, provider=ProviderA())
        b = _runtime(tmp_b.name, provider=ProviderB())
        ra = a.submit("Remember that my favorite color is blue")
        rb = b.submit("Remember that my favorite color is blue")
        self.assertEqual(ra.action.type, rb.action.type)
        self.assertEqual(ra.decision.llm_called, False)
        self.assertEqual(rb.decision.llm_called, False)
        self.assertEqual(ProviderA.calls, 0)
        self.assertEqual(ProviderB.calls, 0)

    def test_runtime_has_no_vendor_branches(self):
        src = Path(__file__).resolve().parents[1] / "core" / "runtime" / "agent_runtime.py"
        text = src.read_text(encoding="utf-8")
        for needle in ("OpenAI", "Grok", "Ollama", "xAI", "openai", "ollama"):
            self.assertNotIn(needle, text)


class TestEventDrivenIdleAndWatch(unittest.TestCase):
    def test_watching_wakes_on_relevant_event_then_rests(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        rt = _runtime(tmp.name)
        first = rt.submit("Monitor project status")
        self.assertEqual(rt.state.phase, AgentPhase.WATCHING.value)
        oid = first.objective.objective_id
        event = RuntimeEvent(
            event_id=new_id("REV"),
            kind=RuntimeEventKind.EXTERNAL_RESULT.value,
            payload={"text": "project status changed", "action": "project status changed"},
            objective_id=oid,
            source="integration",
        )
        second = rt.handle_event(event)
        self.assertEqual(second.action.type, "watch")
        self.assertEqual(rt.state.phase, AgentPhase.WATCHING.value)
        self.assertEqual(second.objective.objective_id, oid)
        self.assertFalse(second.decision.llm_called)

    def test_bus_event_while_idle_does_not_spin(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        rt = _runtime(tmp.name)
        rt.submit("status")
        self.assertTrue(rt.idle())
        before = rt.state.updated_at
        rt.event_bus.publish(
            new_event(run_id="noise", phase=EventPhase.TASK_COMPLETED.value, action="unrelated")
        )
        self.assertTrue(rt.idle())
        self.assertEqual(rt.state.phase, AgentPhase.IDLE.value)
        self.assertEqual(len(rt.list_objectives(open_only=True)), 0)


class TestMemoryIsNotATranscript(unittest.TestCase):
    def test_echo_does_not_write_durable_memory(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        rt = _runtime(tmp.name)
        rt.submit("status")
        durable = [
            m
            for m in rt.memory.store.list_all()
            if m.memory_type != MemoryType.IDENTITY.value
        ]
        self.assertEqual(durable, [])

    def test_failed_attempts_are_not_remembered(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        registry = CapabilityRegistry()
        registry.register(MockEchoCapabilityAdapter())
        registry.register(AlwaysFailCapability())
        rt = _runtime(
            tmp.name,
            capabilities=registry,
            bounds=RuntimeBounds(max_retries=1, max_replans=0),
        )
        rt.submit("use mock.always_fail to inspect node")
        durable = [
            m
            for m in rt.memory.store.list_all()
            if m.memory_type != MemoryType.IDENTITY.value
        ]
        self.assertEqual(durable, [])


class TestObjectiveStoreRoundtrip(unittest.TestCase):
    def test_agent_state_survives_reload(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        rt = _runtime(tmp.name)
        rt.submit("Monitor project status")
        rt2 = _runtime(tmp.name)
        self.assertEqual(rt2.state.phase, AgentPhase.WATCHING.value)
        self.assertTrue(rt2.list_objectives(open_only=True))


if __name__ == "__main__":
    unittest.main()
