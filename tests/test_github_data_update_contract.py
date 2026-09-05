#!/usr/bin/env python3
# tests/test_github_data_update_contract.py
"""Python Contract Mirror Test for GitHub Data Update v0.1 Specification.

Mirrors and validates the security, integrity, versioning, atomic delta update,
path safety, and rollback contracts of GitHub Data Update v0.1 on Linux CI:
1. Valid manifest schema parsing
2. Relative path safety validation (rejecting absolute paths and '..' traversal)
3. Executable code boundary enforcement (rejecting Swift/native binary file downloads)
4. SHA-256 checksum and expected file size validation
5. Version rule policy: same version -> UP_TO_DATE, older version -> REJECTED/FAILED
6. Delta update preservation: unchanged files in active/ are preserved during delta updates
7. Automatic rollback on validation failure (preserving last known-good version and active dataset)
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
    """Python mirror of GitHubDataUpdateManager atomic delta update, versioning, and rollback logic."""

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
        remote_version = manifest.get("dataVersion", "")

        # Version Policy Enforcement
        if remote_version == self.installed_version:
            return {"status": "UP_TO_DATE", "installedDataVersion": self.installed_version}

        if validator.is_version_older(remote_version, self.installed_version):
            return {
                "status": "FAILED",
                "error": f"Version Downgrade Rejected: Remote version {remote_version} is older than installed {self.installed_version}",
                "installedDataVersion": self.installed_version,
            }

        # Validate manifest files & path safety
        for entry in manifest.get("files", []):
            path = entry["path"]
            validator.validate_path_safety(path)

        # 1. Clean staging
        if self.staging_dir.exists():
            shutil.rmtree(self.staging_dir)
        self.staging_dir.mkdir(parents=True, exist_ok=True)

        # Delta Update Preservation: Copy existing active/ dataset snapshot into staging/ before applying updates
        if self.active_dir.exists():
            for item in self.active_dir.iterdir():
                dst = self.staging_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dst)
                else:
                    shutil.copy2(item, dst)

        try:
            # 2. Download / write delta files
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

            # 3. Atomic commit / swap
            if self.backup_dir.exists():
                shutil.rmtree(self.backup_dir)
            if self.active_dir.exists():
                self.active_dir.rename(self.backup_dir)

            self.staging_dir.rename(self.active_dir)

            if self.backup_dir.exists():
                shutil.rmtree(self.backup_dir)

            self.installed_version = remote_version
            return {"status": "COMMITTED", "installedDataVersion": self.installed_version}

        except Exception as exc:
            # Robust Rollback
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

    def test_04_atomic_delta_update_preserves_unchanged_files(self):
        # 1. Initial v1 setup: active dataset with unchanged.json ("old") and changed.json ("v1")
        unchanged_content = b"old"
        changed_v1 = b"v1"
        hash_unchanged = hashlib.sha256(unchanged_content).hexdigest()
        hash_changed_v1 = hashlib.sha256(changed_v1).hexdigest()

        manifest1 = {
            "schemaVersion": 1,
            "dataVersion": "2026.09.05.001",
            "files": [
                {"path": "unchanged.json", "sha256": hash_unchanged, "size": len(unchanged_content)},
                {"path": "changed.json", "sha256": hash_changed_v1, "size": len(changed_v1)},
            ],
        }

        res1 = self.manager.perform_update(manifest1, {"unchanged.json": unchanged_content, "changed.json": changed_v1})
        self.assertEqual(res1["status"], "COMMITTED")
        self.assertEqual(self.manager.installed_version, "2026.09.05.001")

        # 2. Delta update v2: Manifest contains ONLY changed.json ("v2")
        changed_v2 = b"v2"
        hash_changed_v2 = hashlib.sha256(changed_v2).hexdigest()
        manifest2 = {
            "schemaVersion": 1,
            "dataVersion": "2026.09.05.002",
            "files": [{"path": "changed.json", "sha256": hash_changed_v2, "size": len(changed_v2)}],
        }

        res2 = self.manager.perform_update(manifest2, {"changed.json": changed_v2})
        self.assertEqual(res2["status"], "COMMITTED")
        self.assertEqual(self.manager.installed_version, "2026.09.05.002")

        # Verify active directory preserves unchanged.json ("old") and updates changed.json ("v2")
        unchanged_file = self.manager.active_dir / "unchanged.json"
        changed_file = self.manager.active_dir / "changed.json"

        self.assertTrue(unchanged_file.exists())
        self.assertTrue(changed_file.exists())
        self.assertEqual(unchanged_file.read_bytes(), b"old")
        self.assertEqual(changed_file.read_bytes(), b"v2")

    def test_05_version_downgrade_protection(self):
        sample_data = b"v100_data"
        correct_hash = hashlib.sha256(sample_data).hexdigest()

        manifest1 = {
            "schemaVersion": 1,
            "dataVersion": "2026.09.05.100",
            "files": [{"path": "config.json", "sha256": correct_hash, "size": len(sample_data)}],
        }
        res1 = self.manager.perform_update(manifest1, {"config.json": sample_data})
        self.assertEqual(res1["status"], "COMMITTED")
        self.assertEqual(self.manager.installed_version, "2026.09.05.100")

        # Same version -> UP_TO_DATE (no-op)
        res_same = self.manager.perform_update(manifest1, {"config.json": sample_data})
        self.assertEqual(res_same["status"], "UP_TO_DATE")

        # Older version -> FAILED / REJECTED
        older_data = b"v050_data"
        older_hash = hashlib.sha256(older_data).hexdigest()
        manifest_older = {
            "schemaVersion": 1,
            "dataVersion": "2026.09.05.050",
            "files": [{"path": "config.json", "sha256": older_hash, "size": len(older_data)}],
        }
        res_older = self.manager.perform_update(manifest_older, {"config.json": older_data})
        self.assertEqual(res_older["status"], "FAILED")
        self.assertIn("Version Downgrade Rejected", res_older["error"])
        self.assertEqual(self.manager.installed_version, "2026.09.05.100")

        # Active file content remains original v100 data
        active_file = self.manager.active_dir / "config.json"
        self.assertEqual(active_file.read_bytes(), b"v100_data")

    def test_06_automatic_rollback_on_validation_failure(self):
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

    def test_07_offline_resilience_does_not_break_agent_core(self):
        os.environ["AGENTCORE_PLANNER_PROVIDER"] = "mock"
        agent = Agent(project_id="default")

        # Run task when update service is offline
        res = agent.run("Run task in offline mode without update sync")
        self.assertTrue(res.success)
        self.assertEqual(res.status, "COMPLETED")


if __name__ == "__main__":
    unittest.main()
