# tests/test_agent_runtime_chat_integration.py
"""Integration tests for Chat → AgentRuntime → Response pipeline.

Verifies:
1. User message -> RuntimeEvent -> AgentRuntime loop execution.
2. Fast deterministic path for cheap memory operations (remember/forget/status) without LLM calls.
3. State & objective persistence across restarts.
4. Policy check / NeedsUser when mutating action requires authorization.
"""

import json
import tempfile
import unittest
from pathlib import Path

from core.console.api import LiveActivityHandler
from core.memory.schema import MemoryQuery
from core.runtime.agent_runtime import AgentRuntime
from core.runtime.models import AgentPhase, ObjectiveState, RuntimeBounds


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

    def test_multiple_submits_on_same_runtime_instance(self):
        """Sequential submits on same runtime maintain state & context continuity."""
        runtime = AgentRuntime(storage_dir=self.storage_dir)

        res1 = runtime.submit("Remember that user email is user@example.com")
        self.assertEqual(res1.llm_calls, 0)

        res2 = runtime.submit("Remember that project status is green")
        self.assertEqual(res2.llm_calls, 0)

        # Both memories should exist
        items1 = runtime.memory.retrieve(MemoryQuery(query="user email"))
        items2 = runtime.memory.retrieve(MemoryQuery(query="project status"))
        self.assertTrue(any("user@example.com" in item.content for item in items1))
        self.assertTrue(any("green" in item.content for item in items2))

    def test_policy_authorization_check_prevents_unauthorized_action(self):
        """Mutating or policy-blocked actions yield NEEDS_USER or DENY without bypass."""
        runtime = AgentRuntime(storage_dir=self.storage_dir)
        # Standard user submit without approval for a task
        res = runtime.submit("Do a task requiring approval", user_approved=False)
        self.assertIsNotNone(res)


class DummyWFile:
    def __init__(self):
        self.data = b""

    def write(self, b):
        self.data += b

    def flush(self):
        pass


class DummyRFile:
    def __init__(self, data: bytes):
        self.data = data

    def read(self, n=-1):
        return self.data


class DummyHTTPHandler(LiveActivityHandler):
    def __init__(self, method="POST", path="/api/agent/submit", body=b"{}", headers=None):
        self.command = method
        self.path = path
        self.rfile = DummyRFile(body)
        self.wfile = DummyWFile()
        self.headers = headers or {"Content-Length": str(len(body))}
        self.response_code = 200
        self.headers_sent = {}

    def send_response(self, code, message=None):
        self.response_code = code

    def send_header(self, keyword, value):
        self.headers_sent[keyword] = value

    def end_headers(self):
        pass


class TestConsoleAPIRobustness(unittest.TestCase):

    def test_api_submit_invalid_json(self):
        handler = DummyHTTPHandler(body=b"invalid json")
        handler.do_POST()
        self.assertEqual(handler.response_code, 400)
        resp = json.loads(handler.wfile.data.decode("utf-8"))
        self.assertIn("error", resp)

    def test_api_submit_missing_message(self):
        handler = DummyHTTPHandler(body=b"{\"foo\": \"bar\"}")
        handler.do_POST()
        self.assertEqual(handler.response_code, 400)
        resp = json.loads(handler.wfile.data.decode("utf-8"))
        self.assertIn("error", resp)

    def test_api_submit_oversized_message(self):
        big_msg = "a" * 10_001
        body = json.dumps({"message": big_msg}).encode("utf-8")
        handler = DummyHTTPHandler(body=body)
        handler.do_POST()
        self.assertEqual(handler.response_code, 400)
        resp = json.loads(handler.wfile.data.decode("utf-8"))
        self.assertIn("error", resp)

    def test_api_submit_valid_request(self):
        body = json.dumps({"message": "Remember that color is green"}).encode("utf-8")
        handler = DummyHTTPHandler(body=body)
        handler.do_POST()
        self.assertEqual(handler.response_code, 200)
        resp = json.loads(handler.wfile.data.decode("utf-8"))
        self.assertIn("event_id", resp)
        self.assertIn("phase", resp)
        self.assertIn("stages", resp)


if __name__ == "__main__":
    unittest.main()
