#!/usr/bin/env python3
# tests/test_presentation.py
"""User UI presentation mapper — no Runtime mutations, open phase set."""

import json
import socket
import sys
import tempfile
import time
import unittest
import urllib.request
from http.server import HTTPServer
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.events.schema import new_event
from core.runtime.models import (
    Action,
    AgentPhase,
    AgentState,
    CycleResult,
    ExecutionResult,
    Objective,
    ObjectiveState,
    RuntimeEvent,
)
from core.console.presentation import (
    activity_headline,
    classify_presence,
    present_cycle,
    present_workspace,
    serialize_cycle,
)


class TestPresenceMapping(unittest.TestCase):

    def test_known_phases(self):
        self.assertEqual(classify_presence("IDLE"), "ready")
        self.assertEqual(classify_presence("NEEDS_USER"), "needs_you")
        self.assertEqual(classify_presence("FAILED"), "error")
        self.assertEqual(classify_presence("WATCHING"), "watching")
        self.assertEqual(classify_presence("EXECUTING"), "working")
        self.assertEqual(classify_presence("RETRIEVING"), "working")

    def test_blocked_objective_wins(self):
        self.assertEqual(
            classify_presence("DECIDING", objective_status="BLOCKED"),
            "needs_you",
        )

    def test_unknown_phase_is_working_not_idle(self):
        self.assertEqual(classify_presence("SYNTHESIZING"), "working")
        self.assertEqual(classify_presence("QUANTUM_FOO"), "working")
        self.assertNotEqual(classify_presence("BRAND_NEW_STAGE"), "ready")


class TestActivityCopy(unittest.TestCase):

    def test_phase_copy_is_human(self):
        text = activity_headline(phase="RETRIEVING")
        self.assertIn("thông tin", text.lower())
        self.assertNotIn("RETRIEVE", text)
        self.assertNotIn("CapabilityExecutor", text)

    def test_needs_user_copy(self):
        text = activity_headline(phase="NEEDS_USER")
        self.assertIn("xác nhận", text.lower())
        self.assertNotIn("NEEDS_USER", text)

    def test_mutation_capability_copy(self):
        action = Action(identifier="a1", type="invoke_capability", capability="mock.mutation")
        text = activity_headline(phase="EXECUTING", action=action)
        self.assertIn("cấu hình", text.lower())
        self.assertNotIn("MutationCapability", text)
        self.assertNotIn("ACT", text)

    def test_unknown_phase_does_not_crash(self):
        text = activity_headline(phase="WARP_DRIVE")
        self.assertTrue(text)
        self.assertNotEqual(text.upper(), "WARP_DRIVE")


class TestWorkspaceView(unittest.TestCase):

    def test_idle_workspace_has_user_hierarchy(self):
        view = present_workspace(state=AgentState(), objectives=[])
        self.assertIn("identity", view)
        self.assertIn("objective", view)
        self.assertIn("activity", view)
        self.assertIn("progress", view)
        self.assertIn("result", view)
        self.assertIn("pending_approval", view)
        self.assertIn("history", view)
        self.assertIn("developer", view)
        self.assertEqual(view["identity"]["status"], "ready")
        self.assertNotIn("phase", view["identity"])

    def test_completed_cycle_prioritizes_result(self):
        obj = Objective(objective_id="OBJ-1", intent="Nhớ màu xanh", status=ObjectiveState.COMPLETED.value)
        state = AgentState(phase=AgentPhase.IDLE.value, last_outcome="COMPLETED")
        result = CycleResult(
            event=RuntimeEvent.user_input("Nhớ màu xanh"),
            objective=obj,
            agent_state=state,
            action=Action(identifier="a", type="remember", arguments={"content": "màu xanh"}),
            execution=ExecutionResult(success=True, status="SUCCESS", output={"content": "màu xanh"}),
            stages=["OBSERVE", "UNDERSTAND", "RETRIEVE", "DECIDE", "ACT", "VERIFY", "REMEMBER", "FINISH"],
        )
        presented = present_cycle(result)
        self.assertTrue(presented["result"]["present"])
        self.assertTrue(presented["result"]["ok"])
        self.assertIn("nhớ", presented["result"]["headline"].lower())
        self.assertIsNone(presented["pending_approval"])
        self.assertNotIn("REMEMBERING", presented["result"]["headline"])

    def test_needs_user_exposes_approval_not_phase(self):
        obj = Objective(
            objective_id="OBJ-2",
            intent="Cập nhật cấu hình",
            status=ObjectiveState.BLOCKED.value,
            pending_action={"type": "invoke_capability", "capability": "mock.mutation"},
            last_error="requires user approval",
        )
        state = AgentState(phase=AgentPhase.NEEDS_USER.value, last_outcome="BLOCKED", active_objective_id="OBJ-2")
        view = present_workspace(state=state, objectives=[obj])
        self.assertEqual(view["identity"]["status"], "needs_you")
        self.assertTrue(view["pending_approval"]["present"])
        self.assertIn("xác nhận", view["pending_approval"]["headline"].lower())
        self.assertIsNone(view["result"])
        self.assertNotEqual(view["activity"]["headline"], "NEEDS_USER")

    def test_serialize_cycle_keeps_legacy_fields(self):
        obj = Objective(objective_id="OBJ-3", intent="status", status=ObjectiveState.COMPLETED.value)
        state = AgentState(phase=AgentPhase.IDLE.value, last_outcome="COMPLETED")
        result = CycleResult(
            event=RuntimeEvent.user_input("status"),
            objective=obj,
            agent_state=state,
            stages=["OBSERVE", "FINISH"],
        )
        payload = serialize_cycle(result)
        for key in ("event_id", "objective", "phase", "stages", "outcome", "llm_calls", "error"):
            self.assertIn(key, payload)
        self.assertIn("presentation", payload)
        self.assertIn("identity", payload["presentation"])


class TestUserUiHttp(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from core.console.api import LiveActivityServer
        s = socket.socket()
        s.bind(("", 0))
        port = s.getsockname()[1]
        s.close()
        cls.server = LiveActivityServer(host="127.0.0.1", port=port)
        cls.server.start()
        cls.base = f"http://127.0.0.1:{port}"
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def _get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=5) as r:
            body = r.read().decode("utf-8")
            try:
                return r.status, json.loads(body)
            except json.JSONDecodeError:
                return r.status, {"raw": body}

    def _post(self, path, payload):
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.base + path, data=data, method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status, json.loads(r.read().decode("utf-8"))

    def test_index_is_user_workspace(self):
        code, data = self._get("/")
        self.assertEqual(code, 200)
        html = data["raw"]
        self.assertIn("Personal Agent", html)
        self.assertIn("Mục tiêu hiện tại", html)
        self.assertIn("Live Console", html)
        self.assertIn("composer", html)

    def test_workspace_endpoint_shape(self):
        code, data = self._get("/api/agent/workspace")
        self.assertEqual(code, 200)
        for key in ("identity", "activity", "progress", "result", "pending_approval", "history", "developer"):
            self.assertIn(key, data)
        self.assertNotIn("NEEDS_USER", data["identity"]["status_label"])

    def test_submit_returns_presentation(self):
        code, data = self._post("/api/agent/submit", {"message": "Remember that the harbor is quiet."})
        self.assertEqual(code, 200)
        self.assertIn("phase", data)
        self.assertIn("presentation", data)
        self.assertIn("identity", data["presentation"])
        headline = data["presentation"]["activity"]["headline"]
        self.assertNotIn("CapabilityExecutor", headline)
        result = data["presentation"]["result"]
        self.assertTrue(result is None or result.get("present"))

    def test_js_does_not_hardcode_loop_layout(self):
        code, data = self._get("/app.js")
        self.assertEqual(code, 200)
        js = data["raw"]
        self.assertIn("/api/agent/workspace", js)
        self.assertIn("presentation", js)
        self.assertNotIn("CapabilityExecutor", js)


if __name__ == "__main__":
    unittest.main()
