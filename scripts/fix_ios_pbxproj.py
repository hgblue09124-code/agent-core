#!/usr/bin/env python3
"""DEPRECATED — do not repair project.pbxproj in CI.

Use scripts/validate_ios_pbxproj.py instead. The full project.pbxproj must be
committed in source control with LanguageModelProvider sources registered in
both the app and test PBXSourcesBuildPhase entries.
"""
from __future__ import annotations
import sys

def main() -> int:
    print(
        "fix_ios_pbxproj.py is deprecated. "
        "Commit a complete project.pbxproj and run scripts/validate_ios_pbxproj.py.",
        file=sys.stderr,
    )
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
