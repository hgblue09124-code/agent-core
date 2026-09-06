#!/usr/bin/env python3
# tests/test_ios_zip_package_validation.py
"""Validate the iOS source zip produced from the live ios/ tree."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from scripts.package_ios_source_zip import package_ios_source_zip
from scripts.validate_ios_release_zip import validate_zip


class TestIOSReleaseZipPackageValidation(unittest.TestCase):
    def test_generated_zip_from_live_ios_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "agent-core-ios-source.zip"
            package_ios_source_zip(zip_path)
            self.assertTrue(zip_path.is_file())
            self.assertGreater(zip_path.stat().st_size, 0)
            ok, errors = validate_zip(zip_path)
            self.assertTrue(ok, f"Generated zip validation failed: {errors}")

    def test_missing_zip_is_invalid(self):
        ok, errors = validate_zip(_root / "does-not-exist.zip")
        self.assertFalse(ok)
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
