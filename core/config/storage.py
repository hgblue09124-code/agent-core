# core/config/storage.py
"""Storage directory resolution with environment variable fallback and safety boundaries.

Precedence:
1. Explicit path parameter passed to constructor/method (unconstrained override).
2. AGENTCORE_STORAGE_DIR environment variable (if set and non-empty).
3. Default fallback: ~/.agent-core

Safety Boundaries:
- `get_storage_dir` and `get_storage_path` require relative-only arguments.
- Absolute paths passed to `get_storage_dir` or `get_storage_path` raise ValueError.
- Path traversal outside the configured storage root raises ValueError.
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


def _validate_relative_storage_path(base: Path, path_str: str) -> Path:
    """Validate and resolve a relative path against base storage directory.

    Raises ValueError if:
    - path_str is absolute
    - path_str attempts path traversal outside base storage directory
    """
    if not path_str or not path_str.strip():
        return base

    p = Path(path_str)
    if p.is_absolute():
        raise ValueError(f"Absolute storage path rejected: {path_str!r}. Storage paths must be relative.")

    base_resolved = base.resolve()
    resolved = (base / p).resolve()

    try:
        resolved.relative_to(base_resolved)
    except ValueError:
        raise ValueError(f"Storage path traversal outside base storage root rejected: {path_str!r}")

    return resolved


def get_storage_dir(subfolder: Optional[str] = None) -> Path:
    """Return storage directory for a subsystem.

    Args:
        subfolder: Optional relative subfolder name (e.g., 'knowledge', 'runs').

    Returns:
        Path object for the resolved directory inside the storage root.

    Raises:
        ValueError: If subfolder is absolute or attempts path traversal outside storage root.
    """
    base = get_base_storage_dir()
    if subfolder:
        return _validate_relative_storage_path(base, subfolder)
    return base


def get_storage_path(relative_path: str) -> Path:
    """Return storage path for a specific file.

    Args:
        relative_path: Path relative to base storage dir (e.g., 'evaluation/evidence.json').

    Returns:
        Path object for the resolved file path inside the storage root.

    Raises:
        ValueError: If relative_path is absolute or attempts path traversal outside storage root.
    """
    base = get_base_storage_dir()
    return _validate_relative_storage_path(base, relative_path)
