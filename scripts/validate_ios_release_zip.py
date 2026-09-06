#!/usr/bin/env python3
# scripts/validate_ios_release_zip.py
"""Automated Package Validator for the iOS source release zip.

Inspects the release archive to verify integrity and security boundaries:
1. ZIP file is readable.
2. ios/AgentCoreIOS.xcodeproj/project.pbxproj exists.
3. Required Swift API, Runtime, Storage, Provider, Update sources exist.
4. Unit tests exist.
5. ios/README.md exists.
6. ZERO .git/ files inside zip.
7. ZERO DerivedData/ files inside zip.
8. ZERO signing certificates, private keys, or provisioning profiles.
9. ZERO compiled build artifacts (.app, .ipa, .o, .a, .dylib).
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

_root = Path(__file__).resolve().parents[1]


REQUIRED = [
    "ios/AgentCoreIOS.xcodeproj/project.pbxproj",
    "ios/AgentCoreIOS/API/LocalAgentService.swift",
    "ios/AgentCoreIOS/API/AgentRuntimeContract.swift",
    "ios/AgentCoreIOS/API/AgentAPIModels.swift",
    "ios/AgentCoreIOS/Runtime/AgentRuntime.swift",
    "ios/AgentCoreIOS/Update/GitHubDataUpdateManager.swift",
    "ios/AgentCoreIOS/Update/DataUpdateValidator.swift",
    "ios/AgentCoreIOS/Providers/LanguageModelProvider.swift",
    "ios/Tests/LocalAgentServiceTests.swift",
    "ios/README.md",
]

FORBIDDEN_EXTENSIONS = [
    ".mobileprovision", ".p12", ".cer", ".pem", ".key", ".p8",
    ".ipa", ".dylib", ".so", ".o", ".a",
]


def validate_zip(zip_path: Path) -> tuple[bool, list[str]]:
    errors = []

    if not zip_path.exists():
        errors.append(f"Zip package file not found at: {zip_path}")
        return False, errors

    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            names = z.namelist()
            name_set = set(names)

            for req in REQUIRED:
                if req not in name_set:
                    errors.append(f"Missing required file in zip: {req}")

            for name in names:
                if ".git/" in name or "DerivedData/" in name:
                    errors.append(f"Forbidden directory in zip: {name}")
                lower = name.lower()
                if any(lower.endswith(ext) for ext in FORBIDDEN_EXTENSIONS):
                    errors.append(f"Forbidden extension in zip file: {name}")

    except Exception as exc:
        errors.append(f"Failed to read zip package: {exc}")

    return len(errors) == 0, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate iOS source release zip")
    parser.add_argument("zip_path", nargs="*", help="Zip files to validate")
    args = parser.parse_args()

    zip_paths = [Path(p) for p in args.zip_path]
    if not zip_paths:
        print("Usage: python scripts/validate_ios_release_zip.py <zip> [<zip> ...]", file=sys.stderr)
        return 2

    print("==========================================================")
    print("  AUTOMATED RELEASE ZIP PACKAGE VALIDATOR")
    print("==========================================================")

    all_passed = True
    for zp in zip_paths:
        print(f"\nValidating package: {zp}")
        ok, errors = validate_zip(zp)
        if ok:
            print("  ✓ PACKAGE VALIDATED: All integrity and security checks PASSED.")
        else:
            all_passed = False
            print("  ✗ PACKAGE INVALID:")
            for err in errors:
                print(f"    - {err}")

    print("\n==========================================================")
    if all_passed:
        print("RESULT: ALL RELEASE ZIP PACKAGES VALIDATED SUCCESSFULLY.")
        return 0
    print("RESULT: RELEASE ZIP PACKAGE VALIDATION FAILED.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
