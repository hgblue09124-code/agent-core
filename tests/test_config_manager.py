#!/usr/bin/env python3
# tests/test_config_manager.py
"""ConfigManager v0.5 — minimal tests.

Run: python3 -m unittest tests.test_config_manager -v
"""

import os
import sys
import unittest
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.config.manager import ConfigManager, ProviderConfig


class TestConfigManager(unittest.TestCase):
    """Tests for ConfigManager."""

    def _mgr(self, **env) -> ConfigManager:
        """Build a ConfigManager with given env vars (isolated per-call)."""
        ALL_KEYS = [
            "AGENTCORE_PLANNER_PROVIDER", "AGENTCORE_PLANNER_API_KEY",
            "AGENTCORE_PLANNER_BASE_URL", "AGENTCORE_PLANNER_MODEL",
            "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL",
        ]
        saved = {k: os.environ.get(k) for k in ALL_KEYS}
        for k in ALL_KEYS:
            os.environ.pop(k, None)
        for k, v in env.items():
            os.environ[k] = v
        try:
            return ConfigManager()
        finally:
            for k in ALL_KEYS:
                os.environ.pop(k, None)
            for k, v in saved.items():
                if v is not None and v != "":
                    os.environ[k] = v
                elif v == "" and k in os.environ:
                    pass  # was originally empty, leave clean

    # ── Detection ───────────────────────────────────────────────────

    def test_detects_openai_from_key(self):
        mgr = self._mgr(OPENAI_API_KEY="sk-test", OPENAI_BASE_URL="", OPENAI_MODEL="")
        self.assertEqual(mgr.provider, "openai")

    def test_detects_openrouter_from_env(self):
        mgr = self._mgr(
            AGENTCORE_PLANNER_PROVIDER="openrouter",
            AGENTCORE_PLANNER_API_KEY="sk-or-test",
            AGENTCORE_PLANNER_BASE_URL="https://openrouter.ai/api/v1",
            AGENTCORE_PLANNER_MODEL="gpt-4o",
        )
        self.assertEqual(mgr.provider, "openrouter")

    def test_detects_local(self):
        mgr = self._mgr(
            AGENTCORE_PLANNER_PROVIDER="local",
            AGENTCORE_PLANNER_API_KEY="",
            AGENTCORE_PLANNER_BASE_URL="http://localhost:11434",
            AGENTCORE_PLANNER_MODEL="llama3",
        )
        self.assertEqual(mgr.provider, "local")

    def test_defaults_to_mock(self):
        mgr = self._mgr(AGENTCORE_PLANNER_PROVIDER="mock")
        self.assertEqual(mgr.provider, "mock")

    # ── Validation ───────────────────────────────────────────────────

    def test_mock_is_always_ready(self):
        mgr = self._mgr(AGENTCORE_PLANNER_PROVIDER="mock")
        self.assertTrue(mgr.ready)
        self.assertIsNone(mgr.error)

    def test_openai_missing_key_not_ready(self):
        mgr = self._mgr(
            OPENAI_API_KEY="",
            OPENAI_BASE_URL="https://api.openai.com/v1",
            OPENAI_MODEL="gpt-4o",
        )
        self.assertFalse(mgr.ready)
        self.assertIsNotNone(mgr.error)
        self.assertIn("API key", mgr.error)

    def test_openai_valid_config_ready(self):
        mgr = self._mgr(
            OPENAI_API_KEY="sk-test",
            OPENAI_BASE_URL="https://api.openai.com/v1",
            OPENAI_MODEL="gpt-4o",
        )
        self.assertTrue(mgr.ready)
        self.assertIsNone(mgr.error)

    def test_invalid_base_url_not_ready(self):
        mgr = self._mgr(
            OPENAI_API_KEY="sk-test",
            OPENAI_BASE_URL="not-a-url",
            OPENAI_MODEL="gpt-4o",
        )
        self.assertFalse(mgr.ready)
        self.assertIn("valid HTTP", mgr.error)

    def test_empty_base_url_not_ready(self):
        mgr = self._mgr(
            OPENAI_API_KEY="sk-test",
            OPENAI_BASE_URL="",
            OPENAI_MODEL="gpt-4o",
        )
        self.assertFalse(mgr.ready)
        self.assertIn("Base URL", mgr.error)

    def test_empty_model_not_ready(self):
        mgr = self._mgr(
            OPENAI_API_KEY="sk-test",
            OPENAI_BASE_URL="https://api.openai.com/v1",
            OPENAI_MODEL="",
        )
        self.assertFalse(mgr.ready)
        self.assertIn("Model", mgr.error)

    # ── Secrets stay in memory ───────────────────────────────────────

    def test_api_key_not_in_repr(self):
        mgr = self._mgr(
            OPENAI_API_KEY="sk-secret-xyz",
            OPENAI_BASE_URL="https://api.openai.com/v1",
            OPENAI_MODEL="gpt-4o",
        )
        repr_str = repr(mgr)
        self.assertNotIn("sk-secret-xyz", repr_str)
        self.assertNotIn("secret", repr_str.lower())

    def test_api_key_accessible_via_property(self):
        mgr = self._mgr(
            OPENAI_API_KEY="sk-test",
            OPENAI_BASE_URL="https://api.openai.com/v1",
            OPENAI_MODEL="gpt-4o",
        )
        self.assertEqual(mgr.api_key, "sk-test")

    # ── ProviderConfig dataclass ────────────────────────────────────

    def test_as_provider_config(self):
        mgr = self._mgr(
            OPENAI_API_KEY="sk-test",
            OPENAI_BASE_URL="https://api.openai.com/v1",
            OPENAI_MODEL="gpt-4o",
        )
        cfg = mgr.as_provider_config()
        self.assertIsInstance(cfg, ProviderConfig)
        self.assertEqual(cfg.provider, "openai")
        self.assertEqual(cfg.api_key, "sk-test")
        self.assertEqual(cfg.base_url, "https://api.openai.com/v1")
        self.assertEqual(cfg.model, "gpt-4o")
        self.assertTrue(cfg.ready)
        self.assertIsNone(cfg.error)


if __name__ == "__main__":
    unittest.main()
