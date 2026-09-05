#!/usr/bin/env python3
"""
IPA Release Asset Validator for Agent-Core iOS.

Validates the structure, metadata, and binary integrity of an iOS .ipa archive.
"""

import sys
import zipfile
import plistlib
from pathlib import Path

REQUIRED_BUNDLE_ID = "com.agentcore.AgentCoreIOS"

def validate_ipa(ipa_path: str) -> None:
    path = Path(ipa_path)
    if not path.is_file():
        raise FileNotFoundError(f"IPA file not found: {ipa_path}")

    if path.suffix.lower() != ".ipa":
        raise ValueError(f"File extension must be .ipa, got {path.suffix}")

    try:
        with zipfile.ZipFile(path, "r") as zf:
            namelist = zf.namelist()

            # 1. Must contain Payload/ directory
            payload_entries = [name for name in namelist if name.startswith("Payload/")]
            if not payload_entries:
                raise ValueError("IPA does not contain a 'Payload/' directory.")

            # 2. Locate .app bundle inside Payload/
            app_bundles = set()
            for name in namelist:
                parts = Path(name).parts
                if len(parts) >= 2 and parts[0] == "Payload" and parts[1].endswith(".app"):
                    app_bundles.add(parts[1])

            if not app_bundles:
                raise ValueError("No .app bundle found inside Payload/.")

            app_bundle_name = sorted(list(app_bundles))[0]
            app_name = Path(app_bundle_name).stem
            app_prefix = f"Payload/{app_bundle_name}/"

            # 3. Locate and validate Info.plist
            info_plist_path = f"{app_prefix}Info.plist"
            if info_plist_path not in namelist:
                raise ValueError(f"Info.plist missing at {info_plist_path}")

            info_data = zf.read(info_plist_path)
            try:
                plist = plistlib.loads(info_data)
            except Exception as exc:
                raise ValueError(f"Failed to parse Info.plist: {exc}")

            bundle_id = plist.get("CFBundleIdentifier")
            if not bundle_id:
                raise ValueError("Info.plist missing CFBundleIdentifier")

            if bundle_id != REQUIRED_BUNDLE_ID:
                raise ValueError(f"Bundle ID mismatch: expected '{REQUIRED_BUNDLE_ID}', got '{bundle_id}'")

            version = plist.get("CFBundleShortVersionString")
            if not version:
                raise ValueError("Info.plist missing CFBundleShortVersionString")

            build_num = plist.get("CFBundleVersion")
            if not build_num:
                raise ValueError("Info.plist missing CFBundleVersion")

            # 4. Check executable binary exists and is non-empty
            exec_name = plist.get("CFBundleExecutable", app_name)
            exec_path = f"{app_prefix}{exec_name}"

            if exec_path not in namelist:
                raise ValueError(f"Executable binary missing at {exec_path}")

            exec_info = zf.getinfo(exec_path)
            if exec_info.file_size == 0:
                raise ValueError(f"Executable binary at {exec_path} is empty (0 bytes)")

            print(f"✅ IPA validation successful: {path.name}")
            print(f"   - App Bundle: {app_bundle_name}")
            print(f"   - Bundle ID: {bundle_id}")
            print(f"   - Version: {version} (Build {build_num})")
            print(f"   - Executable Size: {exec_info.file_size} bytes")

    except zipfile.BadZipFile:
        raise ValueError(f"Corrupt or invalid ZIP format in IPA file: {ipa_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_ipa.py <path_to_ipa>")
        sys.exit(1)

    ipa_file = sys.argv[1]
    try:
        validate_ipa(ipa_file)
    except Exception as e:
        print(f"❌ IPA Validation Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
