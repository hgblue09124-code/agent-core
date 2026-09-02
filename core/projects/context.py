# core/projects/context.py
"""Project context loader — reads AGENT.md, ARCHITECTURE.md, and
source-of-truth.md from a registered project.

No LLM required. Pure filesystem reads.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from core.projects.manager import ProjectManager, Project


@dataclass
class ProjectContext:
    """Structured project context."""
    project_id: str
    name: str
    root_path: str
    path_valid: bool
    status: str
    documents: dict
    agent_contract: Optional[str]
    architecture: Optional[str]
    source_of_truth: Optional[str]

    def as_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        """One-line summary."""
        return (
            f"{self.project_id} | {self.name} | "
            f"root={self.root_path} | path_valid={self.path_valid} | "
            f"docs={'+'.join(str(int(v['exists'])) for v in self.documents.values())}"
        )

    def has_all_docs(self) -> bool:
        return all(v["exists"] for v in self.documents.values())

    def missing_docs(self) -> list[str]:
        return [k for k, v in self.documents.items() if not v["exists"]]


def load_project_context(project_id: str) -> Optional[ProjectContext]:
    """Load context for a registered project.

    Args:
        project_id: ID in the registry.

    Returns:
        ProjectContext, or None if project_id not found.

    Raises:
        FileNotFoundError: if a document path is registered but the file
        does not exist.
    """
    manager = ProjectManager()
    raw = manager.load_context(project_id)
    if raw is None:
        return None

    return ProjectContext(
        project_id=raw["project_id"],
        name=raw["name"],
        root_path=raw["root_path"],
        path_valid=raw["path_valid"],
        status=raw["status"],
        documents=raw["documents"],
        agent_contract=raw["agent_contract"],
        architecture=raw["architecture"],
        source_of_truth=raw["source_of_truth"],
    )


def list_all_contexts() -> list[ProjectContext]:
    """Load context for every registered project."""
    manager = ProjectManager()
    return [
        ctx for pid in manager._registry.keys()
        if (ctx := load_project_context(pid)) is not None
    ]


if __name__ == "__main__":
    # Quick demo when run directly
    if len(sys.argv) < 2:
        print("Usage: python -m core.projects.context <project_id>")
        sys.exit(1)

    ctx = load_project_context(sys.argv[1])
    if ctx is None:
        print(f"Project not found: {sys.argv[1]}")
        sys.exit(1)

    print(f"=== {ctx.project_id} ===")
    print(ctx.summary())
    print()
    if ctx.has_all_docs():
        print("All documents present.")
    else:
        print(f"Missing: {ctx.missing_docs()}")
    print()
    for field in ("agent_contract", "architecture", "source_of_truth"):
        content = getattr(ctx, field)
        if content:
            print(f"{field} ({len(content)} chars):")
            print(content[:300].strip())
            print("  ...")
        else:
            print(f"{field}: not available")
        print()
