# core/projects/manager.py
"""Project Manager — minimal project registry and context loader.

Does NOT require LLM. Pure filesystem + JSON operations.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


@dataclass
class Project:
    """Minimal project descriptor."""
    project_id: str
    name: str
    root_path: str
    agent_contract: str = ""       # relative path to AGENT.md
    architecture: str = ""         # relative path to ARCHITECTURE.md
    source_of_truth: str = ""     # relative path to source-of-truth doc
    status: str = "active"        # active | dormant | unknown


class ProjectManager:
    """Registry-backed project loader. No database, no LLM."""

    REGISTRY_NAME = "registry.json"

    def __init__(self, registry_path: Optional[str] = None):
        """Initialize manager.

        Args:
            registry_path: Path to registry.json. Defaults to
                <agent-core>/projects/registry.json.
        """
        if registry_path:
            self.registry_path = Path(registry_path)
        else:
            agent_core = Path(__file__).resolve().parents[2]
            self.registry_path = agent_core / "projects" / self.REGISTRY_NAME

        self._registry: dict[str, dict] = {}
        self._load_registry()

    # ── Registry operations ────────────────────────────────────────────────

    def _load_registry(self) -> None:
        """Load registry from disk, create empty if absent or empty."""
        if self.registry_path.exists():
            try:
                with open(self.registry_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if content.strip():
                    self._registry = json.loads(content).get("projects", {})
                else:
                    self._registry = {}
            except (json.JSONDecodeError, OSError):
                self._registry = {}
        else:
            self._registry = {}

    def _save_registry(self) -> None:
        """Write registry to disk."""
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump(
                {"version": "1.0", "projects": self._registry},
                f,
                indent=2,
                ensure_ascii=False,
            )

    def register(self, project: Project) -> None:
        """Register a project (upsert)."""
        self._registry[project.project_id] = asdict(project)
        self._save_registry()

    def unregister(self, project_id: str) -> bool:
        """Remove a project. Returns True if it existed."""
        if project_id in self._registry:
            del self._registry[project_id]
            self._save_registry()
            return True
        return False

    def list_projects(self) -> list[Project]:
        """Return all registered projects as Project objects."""
        return [Project(**v) for v in self._registry.values()]

    def get(self, project_id: str) -> Optional[Project]:
        """Get a project by ID, or None."""
        data = self._registry.get(project_id)
        return Project(**data) if data else None

    def project_exists(self, project_id: str) -> bool:
        """Check if project_id is in registry."""
        return project_id in self._registry

    # ── Path validation ────────────────────────────────────────────────────

    def validate_path(self, project_id: str) -> tuple[bool, str]:
        """Validate that the registered root_path exists.

        Returns:
            (is_valid, reason)
        """
        project = self.get(project_id)
        if not project:
            return False, f"Project '{project_id}' not found in registry"

        root = Path(project.root_path)
        if not root.exists():
            return False, f"root_path does not exist: {root}"
        if not root.is_dir():
            return False, f"root_path is not a directory: {root}"

        return True, "ok"

    # ── Document location ──────────────────────────────────────────────────

    def locate_document(self, project_id: str, doc_key: str) -> Optional[str]:
        """Locate a document by its doc_key (agent_contract | architecture |
        source_of_truth).

        Returns absolute path if found, else None.
        """
        project = self.get(project_id)
        if not project:
            return None

        rel_path = getattr(project, doc_key, None)
        if not rel_path:
            return None

        abs_path = Path(project.root_path) / rel_path
        return str(abs_path) if abs_path.exists() else None

    def locate_agent_md(self, project_id: str) -> Optional[str]:
        """Find AGENT.md for a project."""
        return self.locate_document(project_id, "agent_contract")

    def locate_architecture_md(self, project_id: str) -> Optional[str]:
        """Find ARCHITECTURE.md for a project."""
        return self.locate_document(project_id, "architecture")

    def locate_source_of_truth_md(self, project_id: str) -> Optional[str]:
        """Find source-of-truth.md for a project."""
        return self.locate_document(project_id, "source_of_truth")

    def locate_all_documents(self, project_id: str) -> dict[str, Optional[str]]:
        """Return paths for all three documents, with existence flag."""
        return {
            "agent_md": self.locate_agent_md(project_id),
            "architecture_md": self.locate_architecture_md(project_id),
            "source_of_truth_md": self.locate_source_of_truth_md(project_id),
        }

    # ── Context loading ─────────────────────────────────────────────────────

    def load_context(self, project_id: str) -> Optional[dict]:
        """Load minimal project context from documents.

        Reads AGENT.md, ARCHITECTURE.md, and source-of-truth.md
        (if they exist) and returns a structured dict.

        Returns None if project_id is not registered.
        Raises FileNotFoundError if a registered document is missing.
        """
        project = self.get(project_id)
        if not project:
            return None

        context: dict = {
            "project_id": project.project_id,
            "name": project.name,
            "root_path": project.root_path,
            "path_valid": Path(project.root_path).exists(),
            "status": project.status,
            "documents": {},
            "agent_contract": None,
            "architecture": None,
            "source_of_truth": None,
        }

        docs = self.locate_all_documents(project_id)

        for key, path in docs.items():
            if path and Path(path).exists():
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                doc_key = {
                    "agent_md": "agent_contract",
                    "architecture_md": "architecture",
                    "source_of_truth_md": "source_of_truth",
                }[key]
                context[doc_key] = content
                context["documents"][key] = {
                    "path": path,
                    "size": len(content),
                    "exists": True,
                }
            else:
                context["documents"][key] = {
                    "path": path,
                    "size": 0,
                    "exists": False,
                }

        return context

    # ── CLI helpers ─────────────────────────────────────────────────────────

    def cli_list(self) -> None:
        """Print list of registered projects to stdout."""
        projects = self.list_projects()
        if not projects:
            print("No projects registered.")
            return
        for p in projects:
            status_flag = "✓" if Path(p.root_path).exists() else "✗"
            print(f"{status_flag} {p.project_id}  ({p.name})  [{p.status}]  — {p.root_path}")

    def cli_inspect(self, project_id: str) -> None:
        """Print detailed project info to stdout."""
        project = self.get(project_id)
        if not project:
            print(f"Project '{project_id}' not found in registry.")
            sys.exit(1)

        root = Path(project.root_path)
        path_ok = root.exists()

        print(f"Project ID   : {project.project_id}")
        print(f"Name         : {project.name}")
        print(f"Root path    : {project.root_path}")
        print(f"Status       : {project.status}")
        print(f"Path valid   : {'yes' if path_ok else 'NO — does not exist'}")
        print()

        docs = self.locate_all_documents(project_id)
        for key, path in docs.items():
            if path and Path(path).exists():
                size = Path(path).stat().st_size
                print(f"  ✓ {key}: {path}  ({size} bytes)")
            else:
                print(f"  ✗ {key}: (not found)")

    def cli_load_context(self, project_id: str) -> None:
        """Print context summary for a project."""
        context = self.load_context(project_id)
        if not context:
            print(f"Project '{project_id}' not found in registry.")
            sys.exit(1)

        print(f"Project     : {context['project_id']}")
        print(f"Name        : {context['name']}")
        print(f"Root path   : {context['root_path']}")
        print(f"Path valid  : {context['path_valid']}")
        print(f"Status      : {context['status']}")
        print()
        for doc_key, info in context["documents"].items():
            flag = "✓" if info["exists"] else "✗"
            print(f"  {flag} {doc_key}: {info['size']} bytes")
        print()
        for field in ("agent_contract", "architecture", "source_of_truth"):
            content = context[field]
            if content:
                preview = content[:200].replace("\n", " ").strip()
                print(f"  {field} ({len(content)} chars): {preview}…")
            else:
                print(f"  {field}: not loaded")
