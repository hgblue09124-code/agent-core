#!/usr/bin/env python3
"""Build the iOS source release zip from the live `ios/` tree.

The zip is a snapshot of HEAD sources — never a checked-in binary.
"""

from __future__ import annotations

import argparse
import os
import zipfile
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
IOS_DIR = _root / "ios"

SKIP_DIR_NAMES = {
    ".git",
    "DerivedData",
    "xcuserdata",
    "__pycache__",
    "build",
}


def iter_ios_files(ios_dir: Path = IOS_DIR) -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(ios_dir):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        for name in filenames:
            if name.endswith((".ipa", ".app", ".mobileprovision", ".p12")):
                continue
            files.append(Path(dirpath) / name)
    return files


def package_ios_source_zip(dest: Path, ios_dir: Path = IOS_DIR) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    files = iter_ios_files(ios_dir)
    if not files:
        raise FileNotFoundError(f"No iOS sources under {ios_dir}")
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            rel = path.relative_to(ios_dir.parent)  # ios/...
            zf.write(path, arcname=str(rel).replace(os.sep, "/"))
    return dest


def default_zip_name(version: str = "0.2.0") -> str:
    v = version[1:] if version.startswith("v") else version
    return f"agent-core-ios-v{v}.zip"


def main() -> int:
    parser = argparse.ArgumentParser(description="Package live ios/ sources into a release zip")
    parser.add_argument(
        "-o",
        "--output",
        default="",
        help="Output zip path (default: dist/agent-core-ios-v<version>.zip)",
    )
    parser.add_argument("--version", default=os.environ.get("AGENTCORE_RELEASE_VERSION", "0.2.0"))
    args = parser.parse_args()
    dest = Path(args.output) if args.output else _root / "dist" / default_zip_name(args.version)
    path = package_ios_source_zip(dest)
    print(f"Wrote {path} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
