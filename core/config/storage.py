# core/config/storage.py
"""Storage directory resolution with environment variable fallback.

Precedence:
1. Explicit path parameter passed to constructor/method.
2. AGENTCORE_STORAGE_DIR environment variable (if set and non-empty).
3. Default fallback: ~/.agent-core
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


ENV_STORAGE_DIR = "AGENTCORE_STORAGE_DIR"
DEFAULT_STORAGE_DIR_NAME = ".agent-core"


def get_base_storage_dir() -> Path:
    """Return base storage directory based on environment fallback rules."""
    env_dir = os.environ.get(ENV_STORAGE_DIR, "").strip()
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    return (Path.home() / DEFAULT_STORAGE_DIR_NAME).resolve()


def get_storage_dir(subfolder: Optional[str] = None) -> Path:
    """Return storage directory for a subsystem.

    Args:
        subfolder: Optional relative subfolder name (e.g., 'knowledge', 'runs').

    Returns:
        Path object for the resolved directory.
    """
    base = get_base_storage_dir()
    if subfolder:
        return base / subfolder
    return base


def get_storage_path(relative_path: str) -> Path:
    """Return storage path for a specific file.

    Args:
        relative_path: Path relative to base storage dir (e.g., 'evaluation/evidence.json').

    Returns:
        Path object for the resolved file path.
    """
    base = get_base_storage_dir()
    return base / relative_path
