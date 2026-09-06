#!/usr/bin/env python3
"""Restore ios/AgentCoreIOS.xcodeproj/project.pbxproj if truncated, then register LanguageModelProvider sources.

Idempotent. Intended to run in CI before xcodebuild, and locally after pulling the PR.

IMPORTANT: This Xcode project compiles app sources into BOTH the app target and the
test target (shared PBXBuildFile IDs). LanguageModelProvider.swift and
MockLanguageModelProvider.swift must appear in BOTH Sources build phases.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PBX = ROOT / "ios" / "AgentCoreIOS.xcodeproj" / "project.pbxproj"

REF_LMP, BUILD_LMP = "004000", "004001"
REF_MOCK, BUILD_MOCK = "004002", "004003"
REF_TEST, BUILD_TEST = "004004", "004005"


def restore_from_master() -> None:
    text = PBX.read_text(encoding="utf-8") if PBX.exists() else ""
    if len(text) >= 10000 and "PBXBuildFile" in text and "rootObject" in text:
        return
    print("project.pbxproj looks truncated/corrupt; restoring from origin/master…")
    for ref in ("origin/master", "master"):
        try:
            content = subprocess.check_output(
                ["git", "show", f"{ref}:ios/AgentCoreIOS.xcodeproj/project.pbxproj"],
                cwd=ROOT,
            )
            PBX.write_bytes(content)
            print(f"Restored via git show {ref} ({len(content)} bytes)")
            return
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    import urllib.request

    url = (
        "https://raw.githubusercontent.com/hgblue09124-code/agent-core/"
        "master/ios/AgentCoreIOS.xcodeproj/project.pbxproj"
    )
    with urllib.request.urlopen(url, timeout=30) as resp:
        content = resp.read()
    PBX.write_bytes(content)
    print(f"Restored via raw.githubusercontent.com ({len(content)} bytes)")


def patch(text: str) -> str:
    # Fully patched when LMP appears in BOTH Sources phases.
    if text.count(f"{BUILD_LMP} /* LanguageModelProvider.swift in Sources */") >= 2:
        print("LanguageModelProvider already in both Sources phases; skipping patch")
        return text

    # If partially patched, restore clean master then re-apply full patch.
    if REF_LMP in text or "LanguageModelProvider.swift" in text:
        print("Partial patch detected; re-restoring master pbxproj before full patch")
        import urllib.request

        url = (
            "https://raw.githubusercontent.com/hgblue09124-code/agent-core/"
            "master/ios/AgentCoreIOS.xcodeproj/project.pbxproj"
        )
        with urllib.request.urlopen(url, timeout=30) as resp:
            text = resp.read().decode("utf-8")

    if "/* End PBXBuildFile section */" not in text:
        raise SystemExit("PBXBuildFile section marker not found")

    text = text.replace(
        "/* End PBXBuildFile section */",
        (
            f"\t\t{BUILD_LMP} /* LanguageModelProvider.swift in Sources */ = "
            f"{{isa = PBXBuildFile; fileRef = {REF_LMP} /* LanguageModelProvider.swift */; }};\n"
            f"\t\t{BUILD_MOCK} /* MockLanguageModelProvider.swift in Sources */ = "
            f"{{isa = PBXBuildFile; fileRef = {REF_MOCK} /* MockLanguageModelProvider.swift */; }};\n"
            f"\t\t{BUILD_TEST} /* LanguageModelProviderTests.swift in Sources */ = "
            f"{{isa = PBXBuildFile; fileRef = {REF_TEST} /* LanguageModelProviderTests.swift */; }};\n"
            "/* End PBXBuildFile section */"
        ),
    )

    text = text.replace(
        "/* End PBXFileReference section */",
        (
            f"\t\t{REF_LMP} /* LanguageModelProvider.swift */ = "
            f"{{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; "
            f"path = LanguageModelProvider.swift; sourceTree = \"<group>\"; }};\n"
            f"\t\t{REF_MOCK} /* MockLanguageModelProvider.swift */ = "
            f"{{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; "
            f"path = MockLanguageModelProvider.swift; sourceTree = \"<group>\"; }};\n"
            f"\t\t{REF_TEST} /* LanguageModelProviderTests.swift */ = "
            f"{{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; "
            f"path = LanguageModelProviderTests.swift; sourceTree = \"<group>\"; }};\n"
            "/* End PBXFileReference section */"
        ),
    )

    old_providers = (
        "\t\t001074 /* Providers */ = {\n"
        "\t\t\tisa = PBXGroup;\n"
        "\t\t\tchildren = (\n"
        "\t\t\t\t001008 /* AgentModelProvider.swift */,\n"
        "\t\t\t\t001010 /* LocalDeterministicPlanner.swift */,\n"
        "\t\t\t);\n"
        "\t\t\tpath = Providers;\n"
        "\t\t\tsourceTree = \"<group>\";\n"
        "\t\t};"
    )
    new_providers = (
        "\t\t001074 /* Providers */ = {\n"
        "\t\t\tisa = PBXGroup;\n"
        "\t\t\tchildren = (\n"
        "\t\t\t\t001008 /* AgentModelProvider.swift */,\n"
        "\t\t\t\t001010 /* LocalDeterministicPlanner.swift */,\n"
        f"\t\t\t\t{REF_LMP} /* LanguageModelProvider.swift */,\n"
        f"\t\t\t\t{REF_MOCK} /* MockLanguageModelProvider.swift */,\n"
        "\t\t\t);\n"
        "\t\t\tpath = Providers;\n"
        "\t\t\tsourceTree = \"<group>\";\n"
        "\t\t};"
    )
    if old_providers not in text:
        raise SystemExit("Providers group pattern not found — pbxproj structure may have changed")
    text = text.replace(old_providers, new_providers)

    text = text.replace(
        "\t\t\t\t001030 /* LocalAgentServiceTests.swift */,",
        (
            "\t\t\t\t001030 /* LocalAgentServiceTests.swift */,\n"
            f"\t\t\t\t{REF_TEST} /* LanguageModelProviderTests.swift */,"
        ),
        1,
    )

    # BOTH Sources phases share the same build-file IDs — inject after every AgentRuntime line.
    marker = "\t\t\t\t001013 /* AgentRuntime.swift in Sources */,"
    injection = (
        "\t\t\t\t001013 /* AgentRuntime.swift in Sources */,\n"
        f"\t\t\t\t{BUILD_LMP} /* LanguageModelProvider.swift in Sources */,\n"
        f"\t\t\t\t{BUILD_MOCK} /* MockLanguageModelProvider.swift in Sources */,"
    )
    occurrences = text.count(marker)
    if occurrences < 2:
        raise SystemExit(f"Expected >=2 AgentRuntime Sources markers, found {occurrences}")
    text = text.replace(marker, injection)  # replace ALL occurrences

    text = text.replace(
        "\t\t\t\t001031 /* LocalAgentServiceTests.swift in Sources */,",
        (
            "\t\t\t\t001031 /* LocalAgentServiceTests.swift in Sources */,\n"
            f"\t\t\t\t{BUILD_TEST} /* LanguageModelProviderTests.swift in Sources */,"
        ),
        1,
    )

    print("Patched LanguageModelProvider sources into project.pbxproj (both targets)")
    return text


def main() -> int:
    if not PBX.parent.exists():
        print(f"Missing {PBX.parent}", file=sys.stderr)
        return 1
    restore_from_master()
    text = PBX.read_text(encoding="utf-8")
    text = patch(text)
    PBX.write_text(text, encoding="utf-8")
    final = PBX.read_text(encoding="utf-8")
    lmp = final.count(f"{BUILD_LMP} /* LanguageModelProvider.swift in Sources */")
    mock = final.count(f"{BUILD_MOCK} /* MockLanguageModelProvider.swift in Sources */")
    tests = final.count(f"{BUILD_TEST} /* LanguageModelProviderTests.swift in Sources */")
    print(f"Final project.pbxproj size: {PBX.stat().st_size} bytes")
    print(f"LanguageModelProvider in Sources phases: {lmp}")
    print(f"MockLanguageModelProvider in Sources phases: {mock}")
    print(f"LanguageModelProviderTests in Sources phases: {tests}")
    if lmp < 2 or mock < 2:
        print("ERROR: expected LMP/Mock in BOTH app and test Sources phases", file=sys.stderr)
        return 1
    if tests < 1:
        print("ERROR: expected LanguageModelProviderTests in test Sources phase", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
