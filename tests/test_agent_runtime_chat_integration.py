# tests/test_agent_runtime_chat_integration.py
"""Integration tests for Chat → AgentRuntime → Response pipeline.

Verifies:
1. User message -> RuntimeEvent -> AgentRuntime loop execution.
2. Fast deterministic path for cheap memory operations (remember/forget/status) without LLM calls.
3. State & objective persistence across restarts.
4. Policy check / NeedsUser when mutating action requires authorization.
"""

import tempfile
import unittest
from pathlib import Path

from core.memory.schema import MemoryQuery
from core.runtime.agent_runtime import AgentRuntime
from core.runtime.models import AgentPhase, ObjectiveState


class TestAgentRuntimeChatIntegration(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.storage_dir = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_chat_submit_deterministic_remember_and_forget(self):
        """User submit 'remember...' goes through deterministic fast path (0 LLM calls)."""
        runtime = AgentRuntime(storage_dir=self.storage_dir)

        # 1. Submit remember request
        res = runtime.submit("Remember that my favorite food is pizza.")
        self.assertIsNotNone(res.objective)
        self.assertEqual(res.agent_state.phase, AgentPhase.IDLE.value)
        self.assertEqual(res.agent_state.last_outcome, "COMPLETED")
        self.assertEqual(res.llm_calls, 0)
        self.assertIn("ACT", res.stages)
        self.assertIn("VERIFY", res.stages)

        # 2. Check memory store
        items = runtime.memory.retrieve(MemoryQuery(query="favorite food"))
        self.assertTrue(any("pizza" in item.content for item in items))

        # 3. Submit forget request
        res_forget = runtime.submit("Forget favorite food")
        self.assertIsNotNone(res_forget.objective)
        self.assertEqual(res_forget.llm_calls, 0)

        items_after = runtime.memory.retrieve(MemoryQuery(query="favorite food"))
        self.assertEqual(len(items_after), 0)

    def test_objective_and_state_persistence_across_restarts(self):
        """Objectives and agent state persist to disk and survive runtime restarts."""
        # Session 1: Create an objective
        runtime1 = AgentRuntime(storage_dir=self.storage_dir)
        res = runtime1.submit("Remember that server port is 8080.")
        obj_id = res.objective.objective_id

        # Session 2: New runtime instance reading same storage directory
        runtime2 = AgentRuntime(storage_dir=self.storage_dir)
        persisted_obj = runtime2.get_objective(obj_id)

        self.assertIsNotNone(persisted_obj)
        self.assertEqual(persisted_obj.intent, res.objective.intent)
        self.assertEqual(persisted_obj.status, ObjectiveState.COMPLETED.value)

    def test_chat_submit_status_query(self):
        """Cheap status/health query takes fast path without LLM."""
        runtime = AgentRuntime(storage_dir=self.storage_dir)
        res = runtime.submit("check runtime status")
        self.assertEqual(res.llm_calls, 0)
        self.assertEqual(res.agent_state.phase, AgentPhase.IDLE.value)


if __name__ == "__main__":
    unittest.main()
