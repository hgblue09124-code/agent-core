#!/usr/bin/env python3
# tests/test_events.py
"""Live Activity Console v1.1 tests."""

import json
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def _ev(**kw):
    from core.events.schema import AgentEvent, new_event
    defaults = dict(
        event_id="ev-1",
        run_id="RUN-1",
        phase="PLAN",
        action="test action",
        status="RUNNING",
    )
    defaults.update(kw)
    return AgentEvent(**defaults)


# ── Schema ───────────────────────────────────────────────────────────

class TestSchema(unittest.TestCase):

    def test_roundtrip(self):
        from core.events.schema import AgentEvent
        e = _ev()
        d = e.to_dict()
        e2 = AgentEvent.from_dict(d)
        self.assertEqual(e.event_id, e2.event_id)
        self.assertEqual(e.phase, e2.phase)
        self.assertEqual(e.status, e2.status)

    def test_short_ts(self):
        from core.events.schema import AgentEvent
        e = _ev(timestamp="2026-01-01T10:21:04.123456+00:00")
        self.assertEqual(e.short_ts(), "10:21:04")

    def test_short_ts_empty(self):
        from core.events.schema import AgentEvent
        e = _ev(timestamp="")
        self.assertEqual(e.short_ts(), "")

    def test_new_event_auto_id(self):
        from core.events.schema import new_event
        e = new_event("RUN-1", "PLAN", "test")
        self.assertTrue(e.event_id.startswith("EV-"))
        self.assertTrue(bool(e.timestamp))
        self.assertEqual(e.run_id, "RUN-1")

    def test_phase_values(self):
        from core.events.schema import EventPhase
        phases = {p.value for p in EventPhase}
        self.assertIn("PLAN", phases)
        self.assertIn("KNOWLEDGE", phases)
        self.assertIn("EXECUTE", phases)
        self.assertIn("RESULT", phases)
        self.assertGreaterEqual(len(phases), 10)

    def test_event_status_values(self):
        from core.events.schema import EventStatus
        statuses = {s.value for s in EventStatus}
        self.assertIn("PASS", statuses)
        self.assertIn("FAIL", statuses)
        self.assertIn("RUNNING", statuses)


# ── Redaction ────────────────────────────────────────────────────────

class TestRedaction(unittest.TestCase):

    def test_scrub_api_key(self):
        from core.events.redaction import scrub_string
        s = scrub_string("token: sk-abcdefghijklmnopqrstuvwxyz12345678")
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", s)
        self.assertIn("[REDACTED]", s)

    def test_scrub_github_token(self):
        from core.events.redaction import scrub_string
        s = scrub_string("ghp_1234567890abcdefghijklmnop")
        self.assertNotIn("ghp_1234567890", s)

    def test_scrub_password(self):
        from core.events.redaction import scrub_string
        s = scrub_string("password=hunter2")
        self.assertNotIn("hunter2", s)

    def test_scrub_authorization(self):
        from core.events.redaction import scrub_string
        s = scrub_string("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9")
        self.assertNotIn("Bearer", s)
        self.assertIn("[REDACTED]", s)

    def test_scrub_preserves_normal(self):
        from core.events.redaction import scrub_string
        text = "build completed successfully"
        self.assertEqual(scrub_string(text), text)

    def test_redact_event_in_place(self):
        from core.events.redaction import redact_event
        from core.events.schema import AgentEvent
        e = AgentEvent(
            event_id="e1", run_id="R1", phase="PLAN",
            action="token sk-abcdefghijklmnopqrstuvwxyz12345678",
            status="RUNNING",
        )
        redact_event(e)
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", e.action)

    def test_scrub_metadata_sensitive_key(self):
        from core.events.redaction import scrub_metadata
        meta = {"api_key": "sk-secret12345", "description": "normal"}
        out = scrub_metadata(meta)
        self.assertEqual(out["api_key"], "[REDACTED]")
        self.assertEqual(out["description"], "normal")

    def test_scrub_metadata_nested(self):
        from core.events.redaction import scrub_metadata
        meta = {"outer": {"inner": "sk-abcdefghijklmnopqrstuvwxyz12345"}}
        out = scrub_metadata(meta)
        self.assertEqual(out["outer"]["inner"], "[REDACTED]")

    def test_contains_secret(self):
        from core.events.redaction import contains_secret
        self.assertTrue(contains_secret("api_key=sk-abcdefghijk"))
        self.assertFalse(contains_secret("normal text"))

    def test_no_secret_in_event_metadata(self):
        from core.events.schema import AgentEvent
        from core.events.redaction import redact_event
        e = AgentEvent(
            event_id="e1", run_id="R1", phase="EXECUTE",
            action="run",
            status="OK",
            metadata={"password": "hunter2", "count": 42},
        )
        redact_event(e)
        self.assertEqual(e.metadata["password"], "[REDACTED]")
        self.assertEqual(e.metadata["count"], 42)


# ── Event Bus ────────────────────────────────────────────────────────

class TestEventBus(unittest.TestCase):

    def setUp(self):
        from core.events.bus import EventBus
        self.bus = EventBus(max_events=20)

    def test_publish_and_get(self):
        e = _ev()
        self.bus.publish(e)
        self.assertEqual(self.bus.count(), 1)
        retrieved = self.bus.get(e.event_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.phase, "PLAN")

    def test_events_filter_run_id(self):
        self.bus.publish(_ev(run_id="RUN-1"))
        self.bus.publish(_ev(run_id="RUN-2"))
        self.bus.publish(_ev(run_id="RUN-1"))
        evs = self.bus.events(run_id="RUN-1")
        self.assertEqual(len(evs), 2)

    def test_events_filter_phase(self):
        self.bus.publish(_ev(phase="PLAN"))
        self.bus.publish(_ev(phase="EXECUTE"))
        evs = self.bus.events(phase="EXECUTE")
        self.assertEqual(len(evs), 1)

    def test_bounded_buffer(self):
        # publish 25 events with max_events=20
        for i in range(25):
            self.bus.publish(_ev(event_id=f"ev-{i}"))
        self.assertLessEqual(self.bus.count(), 20)

    def test_last_event(self):
        self.bus.publish(_ev(event_id="ev-1"))
        time.sleep(0.01)
        self.bus.publish(_ev(event_id="ev-2"))
        last = self.bus.last()
        self.assertEqual(last.event_id, "ev-2")

    def test_subscribe_and_notify(self):
        received = []
        def handler(ev):
            received.append(ev)

        self.bus.subscribe(handler)
        self.bus.publish(_ev(event_id="ev-sub"))
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].event_id, "ev-sub")

    def test_unsubscribe(self):
        received = []
        def handler(ev):
            received.append(ev)

        self.bus.subscribe(handler)
        self.bus.publish(_ev(event_id="ev-1"))
        self.bus.unsubscribe(handler)
        self.bus.publish(_ev(event_id="ev-2"))
        self.assertEqual(len(received), 1)

    def test_subscriber_exception_does_not_crash(self):
        def bad_handler(ev):
            raise RuntimeError("test error")

        self.bus.subscribe(bad_handler)
        # Should not raise
        self.bus.publish(_ev())
        # Bus should still work
        self.assertEqual(self.bus.count(), 1)

    def test_multiple_subscribers(self):
        r1, r2 = [], []
        def h1(ev): r1.append(ev)
        def h2(ev): r2.append(ev)
        self.bus.subscribe(h1)
        self.bus.subscribe(h2)
        self.bus.publish(_ev(event_id="ev-multi"))
        self.assertEqual(len(r1), 1)
        self.assertEqual(len(r2), 1)

    def test_subscriber_isolation(self):
        """One bad subscriber doesn't stop others."""
        def bad(ev): raise RuntimeError("bad")
        def good(ev): pass
        self.bus.subscribe(bad)
        self.bus.subscribe(good)
        self.bus.publish(_ev())  # should not crash
        self.assertEqual(self.bus.count(), 1)

    def test_redaction_on_publish(self):
        """Secrets are redacted before subscriber sees them."""
        received = []
        def handler(ev):
            received.append(ev)
        self.bus.subscribe(handler)
        self.bus.publish(_ev(
            action="token sk-abcdefghijklmnopqrstuvwxyz12345678"
        ))
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", received[0].action)

    def test_save_and_load(self):
        self.bus.publish(_ev(event_id="ev-s1"))
        self.bus.publish(_ev(event_id="ev-s2"))
        path = tempfile.mktemp(suffix=".json")
        self.addCleanup(lambda: Path(path).unlink(missing_ok=True))
        self.bus.save_to_file(path)

        from core.events.bus import EventBus
        bus2 = EventBus()
        n = bus2.load_from_file(path)
        self.assertEqual(n, 2)

    def test_event_ordering(self):
        """Events are published in order."""
        for i in range(5):
            self.bus.publish(_ev(event_id=f"ev-{i}"))
        evs = self.bus.events()
        ids = [e.event_id for e in evs]
        self.assertEqual(ids, [f"ev-{i}" for i in range(5)])


# ── Global Bus ──────────────────────────────────────────────────────

class TestGlobalBus(unittest.TestCase):

    def test_get_bus_singleton(self):
        from core.events.bus import get_bus, reset_bus
        reset_bus()
        b1 = get_bus()
        b2 = get_bus()
        self.assertIs(b1, b2)

    def test_reset_bus(self):
        from core.events.bus import get_bus, reset_bus
        reset_bus()
        b1 = get_bus()
        b1.publish(_ev())
        reset_bus()
        b2 = get_bus()
        self.assertEqual(b2.count(), 0)


# ── CLI ──────────────────────────────────────────────────────────────

class TestCLI(unittest.TestCase):

    def test_fmt_event(self):
        from core.events.cli import fmt_event
        from core.events.schema import AgentEvent
        e = AgentEvent(
            event_id="e1", run_id="R1", phase="PLAN",
            action="create plan",
            status="RUNNING",
            timestamp="2026-01-01T10:21:04",
        )
        line = fmt_event(e)
        self.assertIn("10:21:04", line)
        self.assertIn("PLAN", line)
        self.assertIn("RUNNING", line)
        self.assertIn("create plan", line)


# ── Kernel Integration ───────────────────────────────────────────────

class TestKernelIntegration(unittest.TestCase):

    def test_kernel_emits_events(self):
        from core.events.bus import EventBus, reset_bus
        from core.kernel.orchestrator import KernelOrchestrator
        reset_bus()
        bus = EventBus()
        o = KernelOrchestrator(event_bus=bus)
        ctx = o.bootstrap("analyze tests", "agent-core")
        self.assertGreater(bus.count(), 0)
        # First event should be BOOTSTRAP/PLAN
        last = bus.last()
        self.assertEqual(last.phase, "PLAN")

    def test_kernel_event_has_run_id(self):
        from core.events.bus import EventBus
        from core.kernel.orchestrator import KernelOrchestrator
        bus = EventBus()
        o = KernelOrchestrator(event_bus=bus)
        ctx = o.bootstrap("test", "p")
        evs = bus.events(run_id=ctx.run_id)
        self.assertGreater(len(evs), 0)

    def test_kernel_events_filterable(self):
        from core.events.bus import EventBus
        from core.kernel.orchestrator import KernelOrchestrator
        bus = EventBus()
        o = KernelOrchestrator(event_bus=bus)
        ctx = o.bootstrap("goal", "p")
        plan_evs = bus.events(phase="PLAN")
        self.assertGreater(len(plan_evs), 0)


# ── Regression ───────────────────────────────────────────────────────

class TestRegression(unittest.TestCase):

    def test_kernel_still_works(self):
        """Kernel v1.0 regression: orchestrator still creates valid context."""
        from core.kernel.orchestrator import KernelOrchestrator
        o = KernelOrchestrator()
        ctx = o.bootstrap("test goal", "p")
        self.assertEqual(ctx.goal, "test goal")
        self.assertEqual(ctx.kernel_status, "RUNNING")
        self.assertTrue(bool(ctx.run_id))

    def test_event_bus_isolation_from_kernel(self):
        """Event bus errors don't crash the kernel."""
        from core.events.bus import EventBus
        from core.kernel.orchestrator import KernelOrchestrator

        bus = EventBus()
        # Add a subscriber that raises
        bus.subscribe(lambda ev: (_ for _ in ()).throw(RuntimeError("crash")))
        o = KernelOrchestrator(event_bus=bus)
        # Should not raise
        ctx = o.bootstrap("test", "p")
        self.assertIsNotNone(ctx)


if __name__ == "__main__":
    unittest.main()
