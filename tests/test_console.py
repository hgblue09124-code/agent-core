#!/usr/bin/env python3
# tests/test_console.py
"""Live Activity Console API tests."""

import json
import socket
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from http.server import HTTPServer
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def _free_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# ── Helper: HTTP test client ──────────────────────────────────────────

class HttpTestClient:
    def __init__(self, base: str):
        self.base = base.rstrip("/")

    def get(self, path: str) -> tuple[int, dict]:
        url = self.base + path
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                body = r.read().decode("utf-8")
                try:
                    return r.status, json.loads(body)
                except json.JSONDecodeError:
                    return r.status, {"raw": body}
        except urllib.error.HTTPError as e:
            return e.code, {"error": e.read().decode("utf-8")}


# ── Test: API health ──────────────────────────────────────────────────

class TestAPIHealth(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from core.console.api import LiveActivityServer
        from core.events.bus import reset_bus
        reset_bus()
        port = _free_port()
        cls.server = LiveActivityServer(host="127.0.0.1", port=port)
        cls.server.start()
        cls.base = f"http://127.0.0.1:{port}"
        cls.client = HttpTestClient(cls.base)
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_health(self):
        code, data = self.client.get("/api/healthz")
        self.assertEqual(code, 200)
        self.assertEqual(data["status"], "ok")
        self.assertIn("events_in_buffer", data)


# ── Test: Events endpoint ────────────────────────────────────────────

class TestAPIEvents(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from core.console.api import LiveActivityServer
        from core.events.bus import reset_bus
        reset_bus()
        port = _free_port()
        cls.server = LiveActivityServer(host="127.0.0.1", port=port)
        cls.server.start()
        cls.base = f"http://127.0.0.1:{port}"
        cls.client = HttpTestClient(cls.base)
        time.sleep(0.1)

        # Inject some events
        from core.events.bus import get_bus
        from core.events.schema import new_event
        bus = get_bus()
        for phase, action in [
            ("PLAN", "bootstrap"),
            ("EXECUTE", "task-1"),
            ("VERIFY", "PASS"),
        ]:
            bus.publish(new_event("RUN-TEST-1", phase, action))

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_runs_endpoint(self):
        code, data = self.client.get("/api/runs")
        self.assertEqual(code, 200)
        self.assertIn("runs", data)
        self.assertGreater(data["total"], 0)

    def test_run_info(self):
        code, data = self.client.get("/api/runs/RUN-TEST-1")
        self.assertEqual(code, 200)
        self.assertEqual(data["run_id"], "RUN-TEST-1")
        self.assertGreaterEqual(data["event_count"], 3)

    def test_run_events(self):
        code, data = self.client.get("/api/runs/RUN-TEST-1/events")
        self.assertEqual(code, 200)
        self.assertEqual(data["run_id"], "RUN-TEST-1")
        self.assertEqual(len(data["events"]), 3)

    def test_run_events_with_limit(self):
        code, data = self.client.get("/api/runs/RUN-TEST-1/events?limit=2")
        self.assertEqual(code, 200)
        self.assertLessEqual(len(data["events"]), 2)

    def test_run_not_found(self):
        code, data = self.client.get("/api/runs/NON-EXISTENT")
        self.assertEqual(code, 404)

    def test_run_events_not_found(self):
        code, data = self.client.get("/api/runs/NON-EXISTENT/events")
        # Returns 404 when run has no events
        self.assertIn(code, (404, 200))

    def test_run_result(self):
        code, data = self.client.get("/api/runs/RUN-TEST-1/result")
        self.assertEqual(code, 200)
        self.assertEqual(data["run_id"], "RUN-TEST-1")
        self.assertIn("metrics", data)
        self.assertIn("verification", data)


# ── Test: Empty / no-run state ───────────────────────────────────────

class TestEmptyState(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from core.console.api import LiveActivityServer, _EVENTS_PATH
        from core.events.bus import reset_bus
        # Clean up persisted events file from previous runs
        _EVENTS_PATH.unlink(missing_ok=True)
        reset_bus()
        port = _free_port()
        cls.server = LiveActivityServer(host="127.0.0.1", port=port)
        cls.server.start()
        cls.base = f"http://127.0.0.1:{port}"
        cls.client = HttpTestClient(cls.base)
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_runs_empty(self):
        code, data = self.client.get("/api/runs")
        self.assertEqual(code, 200)
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["runs"], [])

    def test_run_info_not_found(self):
        code, data = self.client.get("/api/runs/EMPTY")
        self.assertEqual(code, 404)

    def test_run_result_not_found(self):
        code, data = self.client.get("/api/runs/EMPTY/result")
        self.assertEqual(code, 404)


# ── Test: Static files ───────────────────────────────────────────────

class TestStaticFiles(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from core.console.api import LiveActivityServer
        port = _free_port()
        cls.server = LiveActivityServer(host="127.0.0.1", port=port)
        cls.server.start()
        cls.base = f"http://127.0.0.1:{port}"
        cls.client = HttpTestClient(cls.base)
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_index_html(self):
        code, data = self.client.get("/")
        self.assertEqual(code, 200)
        self.assertIn("Live Console", data["raw"])

    def test_static_js(self):
        code, data = self.client.get("/app.js")
        self.assertEqual(code, 200)
        self.assertIn("api", data["raw"])

    def test_static_css(self):
        code, data = self.client.get("/style.css")
        self.assertEqual(code, 200)
        self.assertIn("background", data["raw"])

    def test_path_traversal_blocked(self):
        code, data = self.client.get("/../etc/passwd")
        self.assertEqual(code, 404)

    def test_404(self):
        code, data = self.client.get("/nope.txt")
        self.assertEqual(code, 404)


# ── Test: Event → API ────────────────────────────────────────────────

class TestEventToAPI(unittest.TestCase):

    def test_event_propagates_to_api(self):
        from core.console.api import LiveActivityServer
        from core.events.bus import EventBus, reset_bus
        from core.events.schema import new_event
        from core.runtime.engine import RuntimeEngine

        reset_bus()
        bus = EventBus()

        # Patch engine
        from core.console.adapter import patch_runtime_engine
        patch_runtime_engine()

        port = _free_port()
        server = LiveActivityServer(host="127.0.0.1", port=port)
        server.start()
        client = HttpTestClient(f"http://127.0.0.1:{port}")
        time.sleep(0.1)

        try:
            # Publish event directly to the global bus
            from core.events.bus import get_bus
            get_bus().publish(new_event("RUN-INT-1", "EXECUTE", "test task"))
            time.sleep(0.2)

            # API should see it
            code, data = client.get("/api/runs/RUN-INT-1/events")
            self.assertEqual(code, 200)
            self.assertGreater(len(data["events"]), 0)
            self.assertEqual(data["events"][0]["phase"], "EXECUTE")
        finally:
            server.stop()


# ── Test: API → UI (smoke) ───────────────────────────────────────────

class TestAPIToUI(unittest.TestCase):
    """Simulate browser request flow."""

    @classmethod
    def setUpClass(cls):
        from core.console.api import LiveActivityServer
        from core.events.bus import reset_bus
        from core.events.schema import new_event
        from core.events.bus import get_bus
        reset_bus()
        port = _free_port()
        cls.server = LiveActivityServer(host="127.0.0.1", port=port)
        cls.server.start()
        cls.base = f"http://127.0.0.1:{port}"
        cls.client = HttpTestClient(cls.base)
        time.sleep(0.1)
        bus = get_bus()
        bus.publish(new_event("RUN-UI-1", "PLAN", "create plan"))
        bus.publish(new_event("RUN-UI-1", "EXECUTE", "task done"))
        bus.publish(new_event("RUN-UI-1", "RESULT", "COMPLETED", "OK"))
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_ui_data_flow(self):
        # Simulate what app.js does on init
        code, runs = self.client.get("/api/runs")
        self.assertEqual(code, 200)
        self.assertGreater(runs["total"], 0)

        run_id = runs["runs"][0]["run_id"]
        code, events = self.client.get(f"/api/runs/{run_id}/events")
        self.assertEqual(code, 200)
        self.assertGreater(len(events["events"]), 0)

        code, result = self.client.get(f"/api/runs/{run_id}/result")
        self.assertEqual(code, 200)
        self.assertIn("status", result)
        self.assertIn("verification", result)
        self.assertIn("metrics", result)

        # Static file
        import urllib.request
        resp = urllib.request.urlopen(self.base + "/", timeout=5)
        html = resp.read().decode("utf-8")
        self.assertEqual(resp.status, 200)
        self.assertIn("Live", html)


# ── Test: Secret redaction in API ────────────────────────────────────

class TestSecretRedaction(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from core.console.api import LiveActivityServer
        from core.events.bus import reset_bus
        reset_bus()
        port = _free_port()
        cls.server = LiveActivityServer(host="127.0.0.1", port=port)
        cls.server.start()
        cls.base = f"http://127.0.0.1:{port}"
        cls.client = HttpTestClient(cls.base)
        time.sleep(0.1)

        from core.events.bus import get_bus
        from core.events.schema import new_event
        get_bus().publish(new_event(
            "RUN-SEC-1", "EXECUTE", "deploy",
            metadata={"api_key": "sk-abcdefghijklmnopqrstuvwxyz123456",
                     "password": "hunter2"},
        ))

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_no_secret_in_api(self):
        code, data = self.client.get("/api/runs/RUN-SEC-1/events")
        self.assertEqual(code, 200)
        raw = json.dumps(data)
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz", raw)
        self.assertNotIn("hunter2", raw)
        self.assertIn("[REDACTED]", raw)

    def test_health_no_secret(self):
        code, data = self.client.get("/api/healthz")
        raw = json.dumps(data)
        self.assertNotIn("sk-", raw)
        self.assertNotIn("password", raw)


# ── Test: Disconnected client ────────────────────────────────────────

class TestDisconnectedClient(unittest.TestCase):

    def test_kernel_continues_with_disconnected_client(self):
        """Agent must run even if no client is connected."""
        from core.events.bus import EventBus, reset_bus
        from core.console.adapter import RuntimeEventAdapter

        reset_bus()
        bus = EventBus()

        class FakeEngine:
            pass

        adapter = RuntimeEventAdapter(FakeEngine())
        adapter._bus = bus
        adapter.on_run_start("RUN-DISC-1", "test", "p")
        adapter.on_task_result("RUN-DISC-1", _fake_task("T1"), 0.1)
        adapter.on_verify("RUN-DISC-1", True)

        evs = bus.events(run_id="RUN-DISC-1")
        self.assertGreater(len(evs), 0)


def _fake_task(task_id="T1"):
    from core.tasks.schema import Task, TaskStatus
    return Task(
        task_id=task_id,
        project_id="p",
        title="fake",
        description="",
        status=TaskStatus.COMPLETED,
    )


# ── Test: SSE stream ─────────────────────────────────────────────────

class TestSSEStream(unittest.TestCase):
    """SSE tested via polling fallback: verify stream endpoint is reachable."""

    def test_stream_endpoint_reachable(self):
        """Stream endpoint must respond with event-stream content type."""
        from core.console.api import LiveActivityServer
        from core.events.bus import reset_bus, get_bus
        from core.events.schema import new_event
        import urllib.request

        reset_bus()
        port = _free_port()
        server = LiveActivityServer(host="127.0.0.1", port=port)
        server.start()
        time.sleep(0.1)

        try:
            get_bus().publish(new_event("RUN-SSE-1", "PLAN", "plan started"))
            time.sleep(0.2)

            url = f"http://127.0.0.1:{port}/api/runs/RUN-SSE-1/stream"
            req = urllib.request.Request(url)
            req.add_header("Accept", "text/event-stream")
            with urllib.request.urlopen(req, timeout=3) as r:
                self.assertEqual(r.status, 200)
                ct = r.headers.get("Content-Type", "")
                self.assertIn("text/event-stream", ct)
        finally:
            server.stop()


# ── Test: Adapter ────────────────────────────────────────────────────

class TestAdapter(unittest.TestCase):

    def test_adapter_emits_events(self):
        from core.console.adapter import RuntimeEventAdapter
        from core.events.bus import EventBus, reset_bus
        from core.tasks.schema import Task, TaskStatus
        reset_bus()
        bus = EventBus()

        class FakeEngine:
            pass

        adapter = RuntimeEventAdapter(FakeEngine())
        adapter._bus = bus
        adapter.on_run_start("RUN-AD-1", "goal here", "p")
        adapter.on_task_result("RUN-AD-1", Task(
            task_id="T1", project_id="p", title="t",
            description="", status=TaskStatus.COMPLETED,
        ), 0.5)
        adapter.on_verify("RUN-AD-1", True)
        evs = bus.events(run_id="RUN-AD-1")
        self.assertEqual(len(evs), 3)

    def test_patch_engine(self):
        from core.console.adapter import patch_runtime_engine
        from core.runtime import engine as rt_module
        patch_runtime_engine()
        self.assertTrue(hasattr(rt_module, "_events_patched"))
        # Idempotent
        patch_runtime_engine()
        self.assertTrue(hasattr(rt_module, "_events_patched"))


if __name__ == "__main__":
    unittest.main()
