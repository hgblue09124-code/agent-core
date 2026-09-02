#!/usr/bin/env python3
# core/projects/cli.py
"""Minimal CLI for the project manager.

Usage:
    python -m core.projects.cli list
    python -m core.projects.cli inspect <project_id>
    python -m core.projects.cli load-context <project_id>
    python -m core.projects.cli register <project_id> <name> <root_path>
    python -m core.projects.cli unregister <project_id>
    python -m core.projects.cli validate <project_id>
"""

import sys
from pathlib import Path

# Allow running as script
_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.projects.manager import ProjectManager, Project


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1].lower()
    manager = ProjectManager()

    if cmd == "list":
        manager.cli_list()

    elif cmd == "inspect":
        if len(sys.argv) < 3:
            print("Usage: inspect <project_id>")
            sys.exit(1)
        manager.cli_inspect(sys.argv[2])

    elif cmd == "load-context":
        if len(sys.argv) < 3:
            print("Usage: load-context <project_id>")
            sys.exit(1)
        manager.cli_load_context(sys.argv[2])

    elif cmd == "register":
        if len(sys.argv) < 5:
            print("Usage: register <project_id> <name> <root_path>")
            sys.exit(1)
        project = Project(
            project_id=sys.argv[2],
            name=sys.argv[3],
            root_path=sys.argv[4],
        )
        manager.register(project)
        print(f"Registered: {project.project_id}")

    elif cmd == "unregister":
        if len(sys.argv) < 3:
            print("Usage: unregister <project_id>")
            sys.exit(1)
        ok = manager.unregister(sys.argv[2])
        print(f"Unregistered: {sys.argv[2]}" if ok else f"Not found: {sys.argv[2]}")

    elif cmd == "validate":
        if len(sys.argv) < 3:
            print("Usage: validate <project_id>")
            sys.exit(1)
        valid, reason = manager.validate_path(sys.argv[2])
        print(f"{'VALID' if valid else 'INVALID'}: {reason}")

    elif cmd in ("--help", "-h"):
        print(__doc__)

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
