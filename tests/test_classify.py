#!/usr/bin/env python3
"""Cheap goal classifier."""

from __future__ import annotations

import unittest

from core.runtime.classify import classify_goal, split_fact


class TestClassifyGoal(unittest.TestCase):
    def test_remember(self):
        intent = classify_goal("Remember that my favorite color is blue")
        self.assertTrue(intent.cheap)
        self.assertEqual(intent.kind, "remember")
        self.assertEqual(intent.arguments["value"], "blue")

    def test_forget(self):
        intent = classify_goal("Forget favorite snack")
        self.assertTrue(intent.cheap)
        self.assertEqual(intent.kind, "forget")

    def test_smoke_status(self):
        intent = classify_goal("Verify CI smoke test")
        self.assertTrue(intent.cheap)
        self.assertEqual(intent.kind, "status")

    def test_complex_stays_complex(self):
        intent = classify_goal("Inspect system architecture")
        self.assertFalse(intent.cheap)
        self.assertEqual(intent.kind, "complex")

    def test_split_fact(self):
        key, value = split_fact("my favorite color is blue")
        self.assertIn("color", key.lower())
        self.assertEqual(value, "blue")


if __name__ == "__main__":
    unittest.main()
