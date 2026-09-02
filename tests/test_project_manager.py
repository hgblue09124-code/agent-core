#!/usr/bin/env python3
# tests/test_project_manager.py
"""Tests for core/projects/manager.py and context.py.

Run directly: python tests/test_project_manager.py
Or: python -m pytest tests/test_project_manager.py  (if pytest is installed)

No external dependencies beyond stdlib.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure agent-core root is on path
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.projects.manager import ProjectManager, Project
from core.projects.context import load_project_context, ProjectContext


# ── Fixtures ────────────────────────────────────────────────────────────────

AGENT_CORE_ROOT = _root
PROJECTS_DIR = AGENT_CORE_ROOT / "projects"
REGISTRY_PATH = PROJECTS_DIR / "registry.json"

# The real Cuu-Gioi project root
CUU_GIOI_ROOT = Path("/root/.nanobot/workspace/Cuu-Gioi")


class TestRegistryLoading(unittest.TestCase):
    """Test registry read/write operations."""

    def setUp(self):
        # Use a temp registry for isolation
        self._tmp = tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w"
        )
        self._tmp_path = self._tmp.name
        self._tmp.close()
        self.manager = ProjectManager(registry_path=self._tmp_path)

    def tearDown(self):
        Path(self._tmp_path).unlink(missing_ok=True)

    def test_load_empty_registry(self):
        """Empty registry returns empty list."""
        self.assertEqual(self.manager.list_projects(), [])

    def test_register_and_retrieve(self):
        """Can register a project and retrieve it."""
        p = Project(
            project_id="test-proj",
            name="Test Project",
            root_path="/tmp/test",
            status="active",
        )
        self.manager.register(p)
        retrieved = self.manager.get("test-proj")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.project_id, "test-proj")
        self.assertEqual(retrieved.name, "Test Project")
        self.assertEqual(retrieved.root_path, "/tmp/test")

    def test_register_overwrites(self):
        """Re-registering same ID updates the record."""
        p1 = Project(project_id="x", name="A", root_path="/a")
        p2 = Project(project_id="x", name="B", root_path="/b")
        self.manager.register(p1)
        self.manager.register(p2)
        retrieved = self.manager.get("x")
        self.assertEqual(retrieved.name, "B")
        self.assertEqual(retrieved.root_path, "/b")

    def test_unregister_existing(self):
        """Unregister returns True for existing project."""
        self.manager.register(Project(project_id="y", name="Y", root_path="/y"))
        ok = self.manager.unregister("y")
        self.assertTrue(ok)
        self.assertIsNone(self.manager.get("y"))

    def test_unregister_missing(self):
        """Unregister returns False for missing project."""
        ok = self.manager.unregister("nonexistent")
        self.assertFalse(ok)


class TestProjectLookup(unittest.TestCase):
    """Tests using the real registry."""

    def setUp(self):
        self.manager = ProjectManager()  # uses real registry

    def test_project_cuu_gioi_registered(self):
        """cuu-gioi should be in the registry."""
        self.assertTrue(self.manager.project_exists("cuu-gioi"))

    def test_get_cuu_gioi(self):
        """Can retrieve cuu-gioi metadata."""
        p = self.manager.get("cuu-gioi")
        self.assertIsNotNone(p)
        self.assertEqual(p.project_id, "cuu-gioi")
        self.assertEqual(p.name, "Cửu Giới (Nine Realms)")
        self.assertEqual(p.root_path, str(CUU_GIOI_ROOT))
        self.assertEqual(p.status, "active")

    def test_get_nonexistent_returns_none(self):
        """Unknown project returns None."""
        self.assertIsNone(self.manager.get("this-does-not-exist"))

    def test_list_projects(self):
        """list_projects returns all registered projects."""
        projects = self.manager.list_projects()
        self.assertIsInstance(projects, list)
        self.assertTrue(len(projects) >= 1)
        ids = [p.project_id for p in projects]
        self.assertIn("cuu-gioi", ids)


class TestPathValidation(unittest.TestCase):
    """Tests for path validation."""

    def setUp(self):
        self.manager = ProjectManager()

    def test_cuu_gioi_path_valid(self):
        """cuu-gioi root path should exist."""
        valid, reason = self.manager.validate_path("cuu-gioi")
        self.assertTrue(valid, reason)

    def test_nonexistent_project_invalid(self):
        """Unknown project is invalid."""
        valid, reason = self.manager.validate_path("does-not-exist")
        self.assertFalse(valid)
        self.assertIn("not found", reason)

    def test_nonexistent_root_invalid(self):
        """Project with non-existent root is invalid."""
        tmp_mgr = ProjectManager(
            registry_path=self._mk_temp_registry("/nonexistent/path")
        )
        valid, reason = tmp_mgr.validate_path("fake-proj")
        self.assertFalse(valid)
        self.assertIn("does not exist", reason)

    def _mk_temp_registry(self, root: str) -> str:
        import tempfile
        data = {
            "version": "1.0",
            "projects": {
                "fake-proj": {
                    "project_id": "fake-proj",
                    "name": "Fake",
                    "root_path": root,
                    "status": "active",
                }
            },
        }
        f = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w")
        json.dump(data, f)
        f.close()
        self._temp_files = getattr(self, "_temp_files", [])
        self._temp_files.append(f.name)
        return f.name

    def tearDown(self):
        for f in getattr(self, "_temp_files", []):
            Path(f).unlink(missing_ok=True)


class TestRequiredDocumentDetection(unittest.TestCase):
    """Tests for document location."""

    def setUp(self):
        self.manager = ProjectManager()

    def test_cuu_gioi_agent_md_exists(self):
        """AGENT.md for cuu-gioi should exist."""
        path = self.manager.locate_agent_md("cuu-gioi")
        self.assertIsNotNone(path)
        self.assertTrue(Path(path).exists())
        self.assertTrue(path.endswith("AGENT.md"))

    def test_cuu_gioi_architecture_md_exists(self):
        """ARCHITECTURE.md for cuu-gioi should exist."""
        path = self.manager.locate_architecture_md("cuu-gioi")
        self.assertIsNotNone(path)
        self.assertTrue(Path(path).exists())
        self.assertTrue(path.endswith("ARCHITECTURE.md"))

    def test_cuu_gioi_source_of_truth_exists(self):
        """source-of-truth.md for cuu-gioi should exist."""
        path = self.manager.locate_source_of_truth_md("cuu-gioi")
        self.assertIsNotNone(path)
        self.assertTrue(Path(path).exists())
        self.assertIn("source-of-truth", path)

    def test_nonexistent_project_no_docs(self):
        """Unknown project returns None for all docs."""
        self.assertIsNone(self.manager.locate_agent_md("no-such-proj"))

    def test_locate_all_documents(self):
        """locate_all_documents returns all three with paths."""
        docs = self.manager.locate_all_documents("cuu-gioi")
        self.assertIn("agent_md", docs)
        self.assertIn("architecture_md", docs)
        self.assertIn("source_of_truth_md", docs)
        for key, path in docs.items():
            self.assertIsNotNone(path, f"{key} should not be None")
            self.assertTrue(Path(path).exists(), f"{key} should exist at {path}")


class TestContextLoading(unittest.TestCase):
    """Tests for project context extraction."""

    def setUp(self):
        self.manager = ProjectManager()

    def test_load_context_cuu_gioi(self):
        """Context for cuu-gioi loads successfully."""
        ctx = load_project_context("cuu-gioi")
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.project_id, "cuu-gioi")
        self.assertEqual(ctx.name, "Cửu Giới (Nine Realms)")
        self.assertEqual(ctx.root_path, str(CUU_GIOI_ROOT))
        self.assertTrue(ctx.path_valid)
        self.assertEqual(ctx.status, "active")

    def test_context_has_all_documents(self):
        """cuu-gioi context should have all three documents."""
        ctx = load_project_context("cuu-gioi")
        self.assertTrue(ctx.has_all_docs(), f"Missing: {ctx.missing_docs()}")

    def test_context_doc_content_is_readable(self):
        """Documents should contain real content (not empty)."""
        ctx = load_project_context("cuu-gioi")
        for field in ("agent_contract", "architecture", "source_of_truth"):
            content = getattr(ctx, field)
            self.assertIsNotNone(content, f"{field} should not be None")
            self.assertGreater(
                len(content), 500,
                f"{field} should have substantial content"
            )

    def test_context_agent_md_contains_agent_md(self):
        """AGENT.md content should contain the AI Engineering Contract title."""
        ctx = load_project_context("cuu-gioi")
        self.assertIn("AI Engineering Contract", ctx.agent_contract)

    def test_context_architecture_contains_real_architecture(self):
        """ARCHITECTURE.md content should contain Cửu Giới references."""
        ctx = load_project_context("cuu-gioi")
        self.assertIn("Cửu Giới", ctx.architecture)

    def test_context_source_of_truth_has_table(self):
        """source-of-truth.md should contain the truth table."""
        ctx = load_project_context("cuu-gioi")
        self.assertIn("source of truth", ctx.source_of_truth.lower())

    def test_context_nonexistent(self):
        """Unknown project returns None."""
        self.assertIsNone(load_project_context("nonexistent-id"))

    def test_project_context_as_dict(self):
        """as_dict() returns a serializable dict."""
        ctx = load_project_context("cuu-gioi")
        d = ctx.as_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["project_id"], "cuu-gioi")
        self.assertIn("documents", d)

    def test_project_context_summary(self):
        """summary() returns a one-line string."""
        ctx = load_project_context("cuu-gioi")
        s = ctx.summary()
        self.assertIsInstance(s, str)
        self.assertIn("cuu-gioi", s)
        self.assertIn("Cửu Giới", s)


class TestEdgeCases(unittest.TestCase):
    """Edge case and error handling tests."""

    def test_manager_with_missing_registry_creates_empty(self):
        """Manager auto-creates an empty registry if file missing."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "missing.json"
            mgr = ProjectManager(registry_path=str(path))
            self.assertEqual(mgr.list_projects(), [])
            # Saving should create the file
            mgr.register(Project("x", "X", "/x"))
            self.assertTrue(path.exists())

    def test_context_nonexistent_raises_file_not_found(self):
        """If doc path is registered but file missing, load_context
        raises FileNotFoundError."""
        with tempfile.TemporaryDirectory() as td:
            fake_path = str(Path(td) / "registry.json")
            data = {
                "version": "1.0",
                "projects": {
                    "orphan": {
                        "project_id": "orphan",
                        "name": "Orphan",
                        "root_path": td,
                        "agent_contract": "AGENT.md",  # won't exist
                        "status": "active",
                    }
                },
            }
            with open(fake_path, "w") as f:
                json.dump(data, f)
            mgr = ProjectManager(registry_path=fake_path)
            # validate_path should say path valid (td exists) but doc missing
            valid, reason = mgr.validate_path("orphan")
            self.assertTrue(valid)  # td exists
            # locate_document returns None since AGENT.md not there
            self.assertIsNone(mgr.locate_agent_md("orphan"))


# ── Test runner ────────────────────────────────────────────────────────────

def run_tests() -> bool:
    """Run all tests, return True if all pass."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
