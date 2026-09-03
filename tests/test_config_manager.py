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

import tempfile
from core.config.manager import ConfigManager, ProviderConfig
from core.config.storage import (
    get_base_storage_dir,
    get_storage_dir,
    get_storage_path,
    ENV_STORAGE_DIR,
)
from core.evaluation.evidence import EvidenceLedger
from core.knowledge.provenance import ProvenanceTracker
from core.knowledge.index import InvertedIndex
from core.knowledge.store import PrimitiveStore
from core.experience.store import ExperienceStore
from core.runtime.checkpoint import CheckpointStore
from core.kernel.lifecycle import KernelLifecycle


class TestStorageConfig(unittest.TestCase):
    """Tests for default storage directory & environment fallback."""

    def setUp(self):
        self._orig_env = os.environ.get(ENV_STORAGE_DIR)

    def tearDown(self):
        if self._orig_env is not None:
            os.environ[ENV_STORAGE_DIR] = self._orig_env
        else:
            os.environ.pop(ENV_STORAGE_DIR, None)

    def test_default_fallback(self):
        os.environ.pop(ENV_STORAGE_DIR, None)
        base = get_base_storage_dir()
        self.assertEqual(base, Path.home() / ".agent-core")
        self.assertEqual(get_storage_dir("runs"), Path.home() / ".agent-core" / "runs")
        self.assertEqual(
            get_storage_path("knowledge/index.json"),
            Path.home() / ".agent-core" / "knowledge" / "index.json",
        )

    def test_environment_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ[ENV_STORAGE_DIR] = tmpdir
            base = get_base_storage_dir()
            self.assertEqual(base, Path(tmpdir).resolve())
            self.assertEqual(get_storage_dir("knowledge"), Path(tmpdir).resolve() / "knowledge")
            self.assertEqual(
                get_storage_path("evaluation/evidence.json"),
                Path(tmpdir).resolve() / "evaluation" / "evidence.json",
            )

    def test_absolute_subfolder_rejected(self):
        with self.assertRaises(ValueError) as cm:
            get_storage_dir("/etc/passwd")
        self.assertIn("Absolute storage path rejected", str(cm.exception))

    def test_absolute_relative_path_rejected(self):
        with self.assertRaises(ValueError) as cm:
            get_storage_path("/var/log/syslog")
        self.assertIn("Absolute storage path rejected", str(cm.exception))

    def test_path_traversal_outside_storage_root_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ[ENV_STORAGE_DIR] = tmpdir
            with self.assertRaises(ValueError) as cm:
                get_storage_path("../outside_file.json")
            self.assertIn("traversal outside base storage root rejected", str(cm.exception))

    def test_nested_valid_relative_path_accepted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ[ENV_STORAGE_DIR] = tmpdir
            p = get_storage_path("a/b/c/data.json")
            self.assertEqual(p, Path(tmpdir).resolve() / "a" / "b" / "c" / "data.json")

    def test_env_storage_dir_is_absolute_and_cwd_independent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            full_path = (Path(tmpdir) / "custom_storage_dir").resolve()
            full_path.mkdir(parents=True, exist_ok=True)
            orig_cwd = os.getcwd()
            try:
                os.environ[ENV_STORAGE_DIR] = str(full_path)
                os.chdir(tmpdir)
                base1 = get_base_storage_dir()
                self.assertTrue(base1.is_absolute())
                self.assertEqual(base1, full_path)

                # Change working directory elsewhere
                os.chdir("/tmp")
                base2 = get_base_storage_dir()
                self.assertEqual(base2, full_path)
            finally:
                os.chdir(orig_cwd)

    def test_empty_or_invalid_env_reverts_to_default(self):
        os.environ[ENV_STORAGE_DIR] = "   "
        base = get_base_storage_dir()
        self.assertEqual(base, Path.home() / ".agent-core")

    def test_explicit_configuration_overrides(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ[ENV_STORAGE_DIR] = "/env/should/not/be/used"
            explicit_path = str(Path(tmpdir) / "custom.json")
            ledger = EvidenceLedger(storage_path=explicit_path)
            self.assertEqual(ledger._path, Path(explicit_path))

            explicit_dir = str(Path(tmpdir) / "custom_store")
            store = PrimitiveStore(store_dir=explicit_dir)
            self.assertEqual(store._dir, Path(explicit_dir))

    def test_core_classes_respect_env_storage_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ[ENV_STORAGE_DIR] = tmpdir

            ledger = EvidenceLedger()
            self.assertEqual(ledger._path, Path(tmpdir) / "evaluation" / "evidence.json")

            prov = ProvenanceTracker()
            self.assertEqual(prov._path, Path(tmpdir) / "knowledge" / "evidence.json")

            idx = InvertedIndex()
            self.assertEqual(idx._path, Path(tmpdir) / "knowledge" / "index.json")

            prims = PrimitiveStore()
            self.assertEqual(prims._dir, Path(tmpdir) / "knowledge")

            exps = ExperienceStore()
            self.assertEqual(exps._dir, Path(tmpdir) / "experience")

            ckpts = CheckpointStore()
            self.assertEqual(ckpts._dir, Path(tmpdir) / "runs")

            klife = KernelLifecycle()
            self.assertEqual(klife._dir, Path(tmpdir) / "kernels")


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
