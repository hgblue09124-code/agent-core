# core/version.py
"""Single version source for Agent-Core (Python package + iOS marketing version)."""

from __future__ import annotations

import os
import re
from typing import Optional

__version__ = "0.1.0-beta"
IOS_MARKETING_VERSION = "0.1.0"


def marketing_version() -> str:
    """iOS CFBundleShortVersionString. Strips a leading 'v' and any -beta suffix."""
    raw = os.environ.get("AGENTCORE_RELEASE_VERSION") or IOS_MARKETING_VERSION
    raw = raw.strip()
    if raw.startswith("v"):
        raw = raw[1:]
    raw = re.sub(r"[-+](?:beta|rc|alpha|dev).*$", "", raw, flags=re.I)
    return raw or IOS_MARKETING_VERSION


def build_number(default: str = "1") -> str:
    return str(os.environ.get("AGENTCORE_BUILD_NUMBER") or os.environ.get("GITHUB_RUN_NUMBER") or default)


def ipa_basename(version: Optional[str] = None, build: Optional[str] = None) -> str:
    ver = version or marketing_version()
    if not ver.startswith("v"):
        ver = "v" + ver
    b = build or build_number()
    return f"AgentCore-iOS-{ver}-b{b}-unsigned.ipa"
