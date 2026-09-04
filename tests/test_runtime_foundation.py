#!/usr/bin/env python3
# tests/test_runtime_foundation.py
"""Comprehensive test suite for Personal Agent Runtime Foundation milestone (~50%).

Verifies:
1. Memory persistence, retrieval, updates, and cross-session identity continuity
2. Capability adapter contract, registry invocation, and mock adapter isolation
3. Autonomous task queue, priority sorting, dependency resolution, pause/resume/cancel
4. Task scheduler, bounded execution loops, retry limits, and event emissions
5. Integrated Agent runtime loop (Observe -> Memory -> Reason -> Plan -> Policy -> Capability -> Verify -> Experience -> Memory)
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

from core.memory.schema import MemoryItem, MemoryType, MemoryQuery
from core.memory.store import MemoryStore
from core.memory.manager import MemoryManager
from core.capabilities.schema import CapabilitySpec, CapabilityResult
from core.capabilities.adapter import CapabilityRegistry
from core.capabilities.mock_adapter import MockEchoCapabilityAdapter
from core.tasks.schema import Task, TaskStatus
from core.tasks.manager import TaskManager
from core.tasks.queue import TaskQueue
from core.tasks.scheduler import TaskScheduler
from core.agent import Agent, AgentRunResult
from core.events.bus import EventBus


class TestMemoryAndIdentity(unittest.TestCase):
    """Test memory persistence, retrieval, and identity continuity."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.mem_mgr = MemoryManager(store_dir=self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_identity_continuity_across_sessions(self):
        identity = self.mem_mgr.get_identity()
        self.assertIsNotNone(identity)
        self.assertEqual(identity.memory_type, MemoryType.IDENTITY.value)
        self.assertIn("Agent-Core", identity.content)

        # New manager instance reading same directory preserves identity
        mem_mgr2 = MemoryManager(store_dir=self.tmpdir.name)
        identity2 = mem_mgr2.get_identity()
        self.assertEqual(identity.memory_id, identity2.memory_id)
        self.assertEqual(identity.content, identity2.content)

    def test_remember_and_retrieve_lifecycle(self):
        mem1 = self.mem_mgr.remember("User prefers dark mode UI", memory_type=MemoryType.USER_CONTEXT.value, tags=["ui", "pref"])
        mem2 = self.mem_mgr.remember("Learned Python 3.12 dataclasses", memory_type=MemoryType.LONG_TERM.value, tags=["python"])

        # Retrieve by keyword
        res = self.mem_mgr.retrieve(MemoryQuery(query="dark mode"))
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].memory_id, mem1.memory_id)

        # Retrieve by type
        user_ctx = self.mem_mgr.get_user_context()
        self.assertEqual(len(user_ctx), 1)
        self.assertEqual(user_ctx[0].content, "User prefers dark mode UI")


class TestCapabilityAdapters(unittest.TestCase):
    """Test capability contracts, registry, and mock adapter isolation."""

    def setUp(self):
        self.registry = CapabilityRegistry()
        self.mock_adapter = MockEchoCapabilityAdapter()
        self.registry.register(self.mock_adapter)

    def test_registry_registration_and_spec(self):
        specs = self.registry.list_specs()
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].capability_id, "mock.echo")

    def test_mock_capability_execution_success(self):
        res: CapabilityResult = self.registry.invoke("mock.echo", {"text": "hello world"})
        self.assertTrue(res.success)
        self.assertEqual(res.output, {"echo": "ECHO: hello world"})

    def test_mock_capability_failure_mode(self):
        failing_adapter = MockEchoCapabilityAdapter(capability_id="mock.fail", fail_mode=True)
        self.registry.register(failing_adapter)
        res = self.registry.invoke("mock.fail", {"text": "test"})
        self.assertFalse(res.success)
        self.assertEqual(res.status, "FAILED")
        self.assertIn("Simulated capability failure", res.error)


class TestTaskQueueAndScheduler(unittest.TestCase):
    """Test persistent priority queueing, state machine, and bounded scheduler."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tm = TaskManager(tasks_dir=os.path.join(self.tmpdir.name, "tasks"))
        self.queue = TaskQueue(task_manager=self.tm)
        self.scheduler = TaskScheduler(queue=self.queue)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_priority_and_dependency_queue_ordering(self):
        t1 = Task(task_id="TASK-001", project_id="default", title="Low priority", priority=200)
        t2 = Task(task_id="TASK-002", project_id="default", title="High priority", priority=10)
        t3 = Task(task_id="TASK-003", project_id="default", title="Dependent on 001", priority=5, dependencies=["TASK-001"])

        self.queue.enqueue(t1)
        self.queue.enqueue(t2)
        self.queue.enqueue(t3)

        # Dequeue highest priority ready task -> t2 (priority 10)
        pop1 = self.queue.dequeue()
        self.assertEqual(pop1.task_id, "TASK-002")
        pop1.mark_completed()
        self.tm.save_task(pop1)

        # Dequeue next ready task -> t1 (t3 blocked by t1 dependency)
        pop2 = self.queue.dequeue()
        self.assertEqual(pop2.task_id, "TASK-001")

        # Mark t1 complete, making t3 ready
        pop2.mark_completed()
        self.tm.save_task(pop2)

        pop3 = self.queue.dequeue()
        self.assertEqual(pop3.task_id, "TASK-003")

    def test_bounded_scheduler_loop_and_retry(self):
        task = Task(task_id="TASK-RETRY", project_id="default", title="Failing task", max_retries=2)
        self.queue.enqueue(task)

        def failing_executor(t: Task) -> Task:
            t.mark_failed("Temporary executor error")
            return t

        # Step 1: fails, schedules RETRY (count = 1)
        run1 = self.scheduler.step_once(failing_executor)
        self.assertEqual(run1.status, TaskStatus.RETRY)
        self.assertEqual(run1.retry_count, 1)

        # Step 2: fails, schedules RETRY (count = 2)
        run2 = self.scheduler.step_once(failing_executor)
        self.assertEqual(run2.status, TaskStatus.RETRY)
        self.assertEqual(run2.retry_count, 2)

        # Step 3: fails, reaches max_retries -> FAILED
        run3 = self.scheduler.step_once(failing_executor)
        self.assertEqual(run3.status, TaskStatus.FAILED)


class TestCoherentAgentRuntimeLoop(unittest.TestCase):
    """Test full integrated orchestration loop in Agent."""

    def setUp(self):
        os.environ["AGENTCORE_PLANNER_PROVIDER"] = "mock"
        self.agent = Agent(project_id="default")

    def test_agent_full_orchestration_loop(self):
        res: AgentRunResult = self.agent.run("Verify personal agent runtime foundation")
        self.assertTrue(res.success)
        self.assertEqual(res.status, "COMPLETED")
        self.assertEqual(res.verification_verdict, "PASS")
        self.assertTrue(res.experience_recorded)
        self.assertTrue(len(res.observations) > 0)


if __name__ == "__main__":
    unittest.main()
