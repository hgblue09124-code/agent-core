#!/usr/bin/env python3
"""project.pbxproj must register LLM provider sources as real file refs."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from scripts.validate_ios_pbxproj import main as validate_pbxproj


class TestIOSPbxproj(unittest.TestCase):
    def test_validator_passes_on_committed_project(self):
        self.assertEqual(validate_pbxproj(), 0)

    def test_file_references_exist_for_new_providers(self):
        text = (_root / "ios" / "AgentCoreIOS.xcodeproj" / "project.pbxproj").read_text(encoding="utf-8")
        for fid, name in (
            ("005000", "ModelCatalog.swift"),
            ("005002", "ModelDownloadManager.swift"),
            ("005004", "OpenAICompatibleProvider.swift"),
            ("005006", "RoutingLanguageModelProvider.swift"),
            ("005010", "LLMProviderTests.swift"),
            ("005020", "Assets.xcassets"),
        ):
            self.assertIn(f"{fid} /* {name} */ = {{isa = PBXFileReference;", text)
        self.assertIn("005011 /* LLMProviderTests.swift in Sources */", text)


if __name__ == "__main__":
    unittest.main()
