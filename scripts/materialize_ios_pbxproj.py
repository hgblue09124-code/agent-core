#!/usr/bin/env python3
"""Write ios/AgentCoreIOS.xcodeproj/project.pbxproj from scripts/pbxproj.b64.* parts."""
from __future__ import annotations
import base64
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PBX = ROOT / "ios" / "AgentCoreIOS.xcodeproj" / "project.pbxproj"
PARTS = sorted((ROOT / "scripts").glob("pbxproj.b64.*"))

def main() -> int:
    if not PARTS:
        print("ERROR: missing scripts/pbxproj.b64.*", flush=True)
        return 1
    b64 = "".join(p.read_text().strip() for p in PARTS)
    data = zlib.decompress(base64.b64decode(b64.encode("ascii")))
    PBX.parent.mkdir(parents=True, exist_ok=True)
    PBX.write_bytes(data)
    print(f"Wrote {PBX} ({len(data)} bytes)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
