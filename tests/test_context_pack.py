#!/usr/bin/env python3
"""Context packer — layered selection, truncation, dedup."""

from __future__ import annotations

import unittest

from core.context.pack import (
    ContextPack,
    build_loop_pack,
    clip,
    compact_tool_output,
    needed_layers,
    select_relevant_slice,
)


class TestNeededLayers(unittest.TestCase):
    def test_default_is_current_task_only(self):
        layers = needed_layers("list github issues")
        self.assertEqual(layers, {"current_task"})

    def test_identity_goal_adds_persistent(self):
        layers = needed_layers("who are you")
        self.assertIn("persistent", layers)
        self.assertIn("current_task", layers)

    def test_architecture_goal_adds_retrieved(self):
        layers = needed_layers("inspect the architecture of the kernel")
        self.assertIn("retrieved", layers)

    def test_tool_output_opt_in(self):
        layers = needed_layers("list github issues", has_tool_output=True)
        self.assertIn("tool_output", layers)


class TestClipAndCompact(unittest.TestCase):
    def test_clip_short(self):
        self.assertEqual(clip("abc", 10), "abc")

    def test_clip_long(self):
        out = clip("x" * 200, 80)
        self.assertLessEqual(len(out), 80)
        self.assertIn("truncated", out)

    def test_compact_keeps_tail(self):
        body = "HEAD-" + ("m" * 4000) + "-TAIL-ERROR"
        out = compact_tool_output(body, max_chars=400)
        self.assertIn("HEAD-", out)
        self.assertIn("TAIL-ERROR", out)
        self.assertIn("truncated", out)
        self.assertLess(len(out), len(body))


class TestSelectRelevantSlice(unittest.TestCase):
    def test_fits_budget(self):
        self.assertEqual(select_relevant_slice("hello", "x", 100), "hello")

    def test_picks_overlapping_section(self):
        doc = "# Intro\nnoise\n\n# Kernel loop\nThe kernel orchestrates retrieval.\n\n# Unrelated\nbanana pie"
        out = select_relevant_slice(doc, "kernel retrieval", max_chars=120)
        self.assertIn("kernel", out.lower())
        self.assertLessEqual(len(out), 120)


class TestContextPackRender(unittest.TestCase):
    def test_github_task_omits_identity(self):
        pack = ContextPack(
            current_task="list github issues",
            persistent="I am Agent-Core identity blob " * 20,
            retrieved="- mem: leftover",
        )
        rendered = pack.select_and_render("list github issues")
        self.assertIn("Current task", rendered)
        self.assertNotIn("Persistent memory", rendered)
        self.assertNotIn("Retrieved", rendered)

    def test_dedup_skips_unchanged_layer(self):
        pack = ContextPack(current_task="inspect architecture")
        first = pack.select_and_render("inspect architecture")
        second = pack.select_and_render("inspect architecture")
        self.assertIn("Current task", first)
        self.assertEqual(second, "")

    def test_build_loop_pack_clips_memories(self):
        class Mem:
            content = "x" * 5000

        pack = build_loop_pack("inspect architecture", memories=[Mem()])
        self.assertLess(len(pack.retrieved), 2000)
        self.assertIn("mem:", pack.retrieved)


if __name__ == "__main__":
    unittest.main()
