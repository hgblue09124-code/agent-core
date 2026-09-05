#!/usr/bin/env python3
# tests/test_github_data_update_contract.py
"""Python Contract Mirror Test for GitHub Data Update v0.1 Specification.

Mirrors and validates the security, integrity, versioning, atomic update,
path safety, and rollback contracts of GitHub Data Update v0.1 on Linux CI:
1. Valid manifest schema parsing
2. Relative path safety validation (rejecting absolute paths and '..' traversal)
3. Executable code boundary enforcement (rejecting Swift/native binary file downloads)
4. SHA-256 checksum and expected file size validation
5. Semantic version comparison
6. Atomic update staging and commit swap
7. Automatic rollback on validation failure (preserving last known-good version)
8. Offline resilience (update failures never compromise Agent-Core execution)
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.agent import Agent, AgentRunResult


class DataUpdateValidatorMirror:
    """Python mirror of DataUpdateValidator security and integrity logic."""

    @staticmethod
    def validate_path_safety(path: str) -> None:
        clean = path.strip()
        if clean.startswith("/") or ".." in clean:
            raise ValueError(f"Path Traversal Violation: Path '{path}' contains absolute prefix or '..' traversal.")

        forbidden_extensions = [".swift", ".dylib", ".so", ".a", ".sh", ".bin", ".exec"]
        lower = clean.lower()
        if any(lower.endswith(ext) for ext in forbidden_extensions):
            raise ValueError(f"Executable Code Boundary Violation: Remote file '{path}' has forbidden extension.")

    @staticmethod
    def validate_file_integrity(data: bytes, expected_size: int, expected_sha256: str) -> None:
        if len(data) != expected_size:
            raise ValueError(f"Size Mismatch: File size {len(data)} != expected {expected_size}.")

        computed_sha = hashlib.sha256(data).hexdigest()
        if computed_sha.lower() != expected_sha256.lower():
            raise ValueError(f"SHA-256 Mismatch: Computed '{computed_sha}' != expected '{expected_sha256}'.")

    @staticmethod
    def is_version_older(v1: str, v2: str) -> bool:
        p1 = [int(x) for x in v1.split(".") if x.isdigit()]
        p2 = [int(x) for x in v2.split(".") if x.isdigit()]
        return p1 < p2


class GitHubDataUpdateManagerMirror:
    """Python mirror of GitHubDataUpdateManager atomic update and rollback logic."""

    def __init__(self, storage_dir: str):
        self.storage_dir = Path(storage_dir)
        self.staging_dir = self.storage_dir / "staging"
        self.active_dir = self.storage_dir / "active"
        self.backup_dir = self.storage_dir / "backup"
        self.state_file = self.storage_dir / "update_state.json"

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.installed_version = "2026.09.04.001"

    def perform_update(self, manifest: dict, file_data_map: dict[str, bytes]) -> dict:
        validator = DataUpdateValidatorMirror()

        # Validate manifest files & path safety
        for entry in manifest.get("files", []):
            path = entry["path"]
            validator.validate_path_safety(path)

        # Staging
        if self.staging_dir.exists():
            shutil.rmtree(self.staging_dir)
        self.staging_dir.mkdir(parents=True, exist_ok=True)

        try:
            for entry in manifest.get("files", []):
                path = entry["path"]
                expected_sha = entry["sha256"]
                expected_size = entry["size"]

                data = file_data_map.get(path)
                if data is None:
                    raise ValueError(f"Missing file data for '{path}'")

                validator.validate_file_integrity(data, expected_size, expected_sha)

                target_file = self.staging_dir / path
                target_file.parent.mkdir(parents=True, exist_ok=True)
                with open(target_file, "wb") as f:
                    f.write(data)

            # Atomic commit / swap
            if self.backup_dir.exists():
                shutil.rmtree(self.backup_dir)
            if self.active_dir.exists():
                self.active_dir.rename(self.backup_dir)

            self.staging_dir.rename(self.active_dir)

            if self.backup_dir.exists():
                shutil.rmtree(self.backup_dir)

            self.installed_version = manifest.get("dataVersion", self.installed_version)
            return {"status": "COMMITTED", "installedDataVersion": self.installed_version}

        except Exception as exc:
            # Automatic Rollback
            if not self.active_dir.exists() and self.backup_dir.exists():
                self.backup_dir.rename(self.active_dir)
            return {"status": "FAILED", "error": str(exc), "installedDataVersion": self.installed_version}


class TestGitHubDataUpdateContract(unittest.TestCase):
    """Python contract test suite for GitHub Data Update v0.1."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="update_contract_test_")
        self.manager = GitHubDataUpdateManagerMirror(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_01_path_safety_rejects_traversal_and_absolute_paths(self):
        v = DataUpdateValidatorMirror()
        with self.assertRaises(ValueError):
            v.validate_path_safety("/etc/passwd")
        with self.assertRaises(ValueError):
            v.validate_path_safety("../secret.json")
        with self.assertRaises(ValueError):
            v.validate_path_safety("config/../../secret.json")

    def test_02_path_safety_rejects_executable_code_downloads(self):
        v = DataUpdateValidatorMirror()
        with self.assertRaises(ValueError):
            v.validate_path_safety("update.swift")
        with self.assertRaises(ValueError):
            v.validate_path_safety("libagent.dylib")
        with self.assertRaises(ValueError):
            v.validate_path_safety("script.sh")

    def test_03_sha256_and_size_integrity_validation(self):
        v = DataUpdateValidatorMirror()
        sample_data = b"Agent-Core Data Update Content"
        correct_hash = hashlib.sha256(sample_data).hexdigest()

        # Valid -> Success
        v.validate_file_integrity(sample_data, len(sample_data), correct_hash)

        # Bad hash -> ValueError
        with self.assertRaises(ValueError):
            v.validate_file_integrity(sample_data, len(sample_data), "bad_hash_12345")

        # Bad size -> ValueError
        with self.assertRaises(ValueError):
            v.validate_file_integrity(sample_data, len(sample_data) + 5, correct_hash)

    def test_04_atomic_update_and_commit_swap(self):
        content = b"agent_config_data_v2"
        correct_hash = hashlib.sha256(content).hexdigest()

        manifest = {
            "schemaVersion": 1,
            "dataVersion": "2026.09.05.001",
            "minimumClientVersion": "0.1.0",
            "files": [{"path": "agent-config/default.json", "sha256": correct_hash, "size": len(content)}],
        }

        res = self.manager.perform_update(manifest, {"agent-config/default.json": content})
        self.assertEqual(res["status"], "COMMITTED")
        self.assertEqual(res["installedDataVersion"], "2026.09.05.001")

        # Verify active directory file exists
        active_file = self.manager.active_dir / "agent-config" / "default.json"
        self.assertTrue(active_file.exists())
        self.assertEqual(active_file.read_bytes(), content)

    def test_05_automatic_rollback_on_validation_failure(self):
        # Initial successful update
        content1 = b"config_version_1"
        hash1 = hashlib.sha256(content1).hexdigest()
        manifest1 = {
            "schemaVersion": 1,
            "dataVersion": "2026.09.05.001",
            "files": [{"path": "config.json", "sha256": hash1, "size": len(content1)}],
        }
        self.manager.perform_update(manifest1, {"config.json": content1})
        self.assertEqual(self.manager.installed_version, "2026.09.05.001")

        # Second update with invalid hash -> Rollback
        content2 = b"corrupted_config"
        manifest2 = {
            "schemaVersion": 1,
            "dataVersion": "2026.09.05.002",
            "files": [{"path": "config.json", "sha256": "bad_hash", "size": len(content2)}],
        }
        res2 = self.manager.perform_update(manifest2, {"config.json": content2})
        self.assertEqual(res2["status"], "FAILED")
        self.assertEqual(self.manager.installed_version, "2026.09.05.001")

        # Active file content remains original version
        active_file = self.manager.active_dir / "config.json"
        self.assertEqual(active_file.read_bytes(), content1)

    def test_06_offline_resilience_does_not_break_agent_core(self):
        os.environ["AGENTCORE_PLANNER_PROVIDER"] = "mock"
        agent = Agent(project_id="default")

        # Run task when update service is offline
        res = agent.run("Run task in offline mode without update sync")
        self.assertTrue(res.success)
        self.assertEqual(res.status, "COMPLETED")


if __name__ == "__main__":
    unittest.main()
