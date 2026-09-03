# core/experience/normalizer.py
"""Normalize raw observations into structured experience data.

This module provides deterministic normalization:
    - Strip secrets
    - Normalize whitespace
    - Extract key-value pairs
    - Detect common patterns (file paths, exit codes, error types)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


# ── Secret scrubbing ──────────────────────────────────────────────

_SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "[REDACTED_API_KEY]"),
    (re.compile(r"AIza[0-9A-Za-z\-_]{20,}"), "[REDACTED_API_KEY]"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"xoxb-[A-Za-z0-9-]{20,}"), "[REDACTED_SLACK_TOKEN]"),
    (re.compile(r"(?i)(password|secret|token)\s*[=:]\s*\S+"), r"\1=[REDACTED]"),
]


def scrub(text: str) -> str:
    """Remove secret-like patterns from text."""
    if not text:
        return ""
    result = text
    for pat, repl in _SECRET_PATTERNS:
        result = pat.sub(repl, result)
    return result


# ── Normalized observation ────────────────────────────────────────

@dataclass
class NormalizedObservation:
    """A single normalized observation."""
    raw: str
    cleaned: str
    exit_code: Optional[int] = None
    duration_seconds: Optional[float] = None
    is_error: bool = False
    is_success: bool = False
    tags: list[str] = None  # e.g. ["file_write", "test"]

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


def normalize_observation(raw: str) -> NormalizedObservation:
    """Normalize a raw observation string."""
    cleaned = scrub(raw)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Detect exit code
    exit_code = None
    m = re.search(r"exit code (\d+)", cleaned, re.IGNORECASE)
    if not m:
        m = re.search(r"exit=(\d+)", cleaned, re.IGNORECASE)
    if m:
        exit_code = int(m.group(1))

    # Detect duration
    duration = None
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:seconds?|s|ms|milliseconds?)", cleaned, re.IGNORECASE)
    if m:
        try:
            duration = float(m.group(1))
        except ValueError:
            pass

    is_error = bool(exit_code and exit_code != 0) or "error" in cleaned.lower()
    is_success = not is_error and ("success" in cleaned.lower() or "pass" in cleaned.lower())

    tags: list[str] = []
    if "test" in cleaned.lower():
        tags.append("test")
    if "file" in cleaned.lower() or "path" in cleaned.lower():
        tags.append("file")
    if "network" in cleaned.lower() or "http" in cleaned.lower():
        tags.append("network")
    if "config" in cleaned.lower():
        tags.append("config")

    return NormalizedObservation(
        raw=raw,
        cleaned=cleaned,
        exit_code=exit_code,
        duration_seconds=duration,
        is_error=is_error,
        is_success=is_success,
        tags=tags,
    )


def normalize_observations(raw_list: list[str]) -> list[NormalizedObservation]:
    """Normalize a list of raw observations."""
    return [normalize_observation(o) for o in raw_list]
