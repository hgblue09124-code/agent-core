# core/projects/__init__.py
"""Project management module for agent-core.

Manages registration, loading, and context extraction for known projects.
"""

from core.projects.manager import ProjectManager

__all__ = ["ProjectManager"]
