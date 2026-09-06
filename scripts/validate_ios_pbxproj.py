#!/usr/bin/env python3
"""Validate ios/AgentCoreIOS.xcodeproj/project.pbxproj integrity for Step 1 sources.

Does NOT repair or rewrite the project file. Fails if the committed pbxproj is
truncated, missing PBXFileReference objects, or missing Sources-phase entries.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PBX = ROOT / "ios" / "AgentCoreIOS.xcodeproj" / "project.pbxproj"

REQUIRED_FILE_REFS = [
    ("005000", "ModelCatalog.swift", "sourcecode.swift"),
    ("005002", "ModelDownloadManager.swift", "sourcecode.swift"),
    ("005004", "OpenAICompatibleProvider.swift", "sourcecode.swift"),
    ("005006", "RoutingLanguageModelProvider.swift", "sourcecode.swift"),
    ("005010", "LLMProviderTests.swift", "sourcecode.swift"),
    ("005020", "Assets.xcassets", "folder.assetcatalog"),
]


def main() -> int:
    if not PBX.exists():
        print(f"ERROR: missing {PBX}", file=sys.stderr)
        return 1
    text = PBX.read_text(encoding="utf-8")
    size = len(text.encode("utf-8"))
    print(f"project.pbxproj size={size}")
    if size < 10000:
        print("ERROR: project.pbxproj looks truncated", file=sys.stderr)
        return 1
    if "rootObject" not in text or "PBXProject" not in text:
        print("ERROR: project.pbxproj missing rootObject/PBXProject", file=sys.stderr)
        return 1
    # Exact build-file markers (avoid matching MockLanguageModelProvider substring)
    lmp = text.count("004001 /* LanguageModelProvider.swift in Sources */")
    mock = text.count("004003 /* MockLanguageModelProvider.swift in Sources */")
    tests = text.count("004005 /* LanguageModelProviderTests.swift in Sources */")
    print(f"LMP markers={lmp} MOCK markers={mock} TEST markers={tests}")
    # 1 PBXBuildFile def + 2 Sources phases = 3 for LMP/Mock; tests = 1 def + 1 phase = 2
    if lmp < 3 or mock < 3:
        print("ERROR: LanguageModelProvider/Mock must be in BOTH app and test Sources phases", file=sys.stderr)
        return 1
    if tests < 2:
        print("ERROR: LanguageModelProviderTests missing from test Sources phase", file=sys.stderr)
        return 1
    catalog = text.count("005001 /* ModelCatalog.swift in Sources */")
    routing = text.count("005007 /* RoutingLanguageModelProvider.swift in Sources */")
    print(f"CATALOG markers={catalog} ROUTING markers={routing}")
    if catalog < 3 or routing < 3:
        print("ERROR: ModelCatalog/RoutingLanguageModelProvider must be in BOTH app and test Sources phases", file=sys.stderr)
        return 1
    llm_tests = text.count("005011 /* LLMProviderTests.swift in Sources */")
    print(f"LLM_TEST markers={llm_tests}")
    if llm_tests < 2:
        print("ERROR: LLMProviderTests must be defined and in the test Sources phase", file=sys.stderr)
        return 1
    if "005021 /* Assets.xcassets in Resources */" not in text:
        print("ERROR: Assets.xcassets missing from Resources phase", file=sys.stderr)
        return 1

    file_ref_ids = set(
        re.findall(r"^\s+([0-9A-F]+) /\*[^*]+\*/ = \{isa = PBXFileReference;", text, re.M)
    )
    build_refs = re.findall(r"isa = PBXBuildFile; fileRef = ([0-9A-F]+) ", text)
    missing_refs = sorted(set(build_refs) - file_ref_ids)
    if missing_refs:
        print(f"ERROR: PBXBuildFile fileRef(s) have no PBXFileReference: {missing_refs}", file=sys.stderr)
        return 1

    for fid, name, ftype in REQUIRED_FILE_REFS:
        needle = (
            f"{fid} /* {name} */ = {{isa = PBXFileReference; lastKnownFileType = {ftype}; path = {name};"
        )
        if needle not in text:
            print(f"ERROR: missing PBXFileReference {fid} {name}", file=sys.stderr)
            return 1

    print("pbxproj integrity OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
