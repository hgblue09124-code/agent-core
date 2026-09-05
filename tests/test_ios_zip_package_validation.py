#!/usr/bin/env python3
# tests/test_ios_zip_package_validation.py
"""Automated Test Suite for Release Zip Package Validation.

Tests validate_zip() from scripts/validate_ios_release_zip.py against agent-core-ios-v0.1.0.zip.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from scripts.validate_ios_release_zip import validate_zip


class TestIOSReleaseZipPackageValidation(unittest.TestCase):
    """Test suite verifying agent-core-ios-v0.1.0.zip release package integrity."""

    def test_release_zip_package_root(self):
        zip_path = Path(_root) / "agent-core-ios-v0.1.0.zip"
        ok, errors = validate_zip(zip_path)
        self.assertTrue(ok, f"Release zip validation failed: {errors}")

    def test_release_zip_package_verification_dir(self):
        zip_path = Path(_root) / "verification" / "releases" / "agent-core-ios-v0.1.0.zip"
        ok, errors = validate_zip(zip_path)
        self.assertTrue(ok, f"Verification release zip validation failed: {errors}")


if __name__ == "__main__":
    unittest.main()
