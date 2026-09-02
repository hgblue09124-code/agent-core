# core/tasks/context.py
"""TaskContext — connects a Task to its project's documentation context.

Bridges TaskManager → ProjectManager → ProjectContext.
No LLM. Pure filesystem.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core.projects.manager import ProjectManager
from core.projects.context import load_project_context as load_proj_context
from core.tasks.schema import Task


@dataclass
class TaskContext:
    """Task + its project context, fully resolved.

    Attributes:
        task: The Task record itself.
        project_id: Same as task.project_id.
        project_exists: Whether the project's root_path exists on disk.
        project_name: Human-readable project name.
        project_root: Absolute path to project root.
        agent_contract: Full text of AGENT.md (or None).
        architecture: Full text of ARCHITECTURE.md (or None).
        source_of_truth: Full text of source-of-truth.md (or None).
        missing_docs: List of doc keys that were registered but not found.
    """
    task: Task
    project_id: str
    project_exists: bool
    project_name: str
    project_root: str
    agent_contract: Optional[str]
    architecture: Optional[str]
    source_of_truth: Optional[str]
    missing_docs: list[str] = field(default_factory=list)
    load_error: Optional[str] = None  # if project not in registry

    def has_all_docs(self) -> bool:
        return len(self.missing_docs) == 0

    def summary(self) -> str:
        return (
            f"{self.task.task_id} | {self.task.title} | "
            f"proj={self.project_id} | status={self.task.status.value} | "
            f"docs={'+' * (3 - len(self.missing_docs))}{'-' * len(self.missing_docs)}"
        )

    def as_dict(self) -> dict:
        return {
            "task_id": self.task.task_id,
            "project_id": self.project_id,
            "project_exists": self.project_exists,
            "project_name": self.project_name,
            "project_root": self.project_root,
            "task_status": self.task.status.value,
            "agent_contract_chars": len(self.agent_contract) if self.agent_contract else 0,
            "architecture_chars": len(self.architecture) if self.architecture else 0,
            "source_of_truth_chars": (
                len(self.source_of_truth) if self.source_of_truth else 0
            ),
            "missing_docs": self.missing_docs,
            "has_all_docs": self.has_all_docs(),
        }


def load_task_context(task: Task) -> TaskContext:
    """Build a TaskContext from a Task.

    Connects to the existing ProjectManager to load project documentation.
    Returns a TaskContext even if the project is unknown (load_error is set).
    """
    proj_mgr = ProjectManager()
    project = proj_mgr.get(task.project_id)

    if project is None:
        return TaskContext(
            task=task,
            project_id=task.project_id,
            project_exists=False,
            project_name=task.project_id,
            project_root="",
            agent_contract=None,
            architecture=None,
            source_of_truth=None,
            load_error=f"Project '{task.project_id}' not found in registry",
        )

    from pathlib import Path
    root = Path(project.root_path)
    proj_ctx = load_proj_context(task.project_id)

    # Collect doc availability
    agent_contract: Optional[str] = None
    architecture: Optional[str] = None
    source_of_truth: Optional[str] = None
    missing_docs: list[str] = []

    if proj_ctx:
        agent_contract = proj_ctx.agent_contract
        architecture = proj_ctx.architecture
        source_of_truth = proj_ctx.source_of_truth
        missing_docs = proj_ctx.missing_docs()

    return TaskContext(
        task=task,
        project_id=task.project_id,
        project_exists=root.exists(),
        project_name=project.name,
        project_root=project.root_path,
        agent_contract=agent_contract,
        architecture=architecture,
        source_of_truth=source_of_truth,
        missing_docs=missing_docs,
    )
