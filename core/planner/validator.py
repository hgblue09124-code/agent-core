# core/planner/validator.py
"""Plan validator — rejects malformed or unsafe plans.

LLM outputs must be validated BEFORE conversion to a Task.
"""

from __future__ import annotations

from typing import Iterable
from core.planner.schema import (
    Plan,
    PlanStep,
    VerificationCriterion,
    PlanComplexity,
    ValidationResult,
    is_valid_step_id,
)


# ── Dangerous command patterns ───────────────────────────────────────────

# Shell metacharacters that suggest injection or shell=True
_FORBIDDEN_SHELL_PATTERNS = [
    "&&", "||", ";", "|",   # chaining / pipes
    ">", ">>", "<",          # redirections
    "$(", "`",                # command substitution
    "rm -rf", "rm -fr",      # destructive
    "sudo ",                  # privilege escalation
    "chmod 777",
    "chown ",
    ":(){:|:&};:",           # fork bomb
]

# Python / shell eval patterns
_FORBIDDEN_PYTHON_PATTERNS = [
    "eval(",
    "exec(",
    "__import__",
    "compile(",
    "globals()",
    "locals()",
    "open('/dev/",           # device access
]

# Blocked / dangerous commands outright
_FORBIDDEN_COMMANDS = {
    "rm", "rmdir", "dd", "mkfs", "fdisk", "shutdown", "reboot",
    "halt", "poweroff", "init", "kill", "killall", "pkill",
    "curl", "wget", "scp", "ssh", "nc", "netcat",
    "su", "sudo", "chmod", "chown", "chgrp", "passwd",
    "iptables", "firewall-cmd", "ufw",
    "systemctl", "service",
    "useradd", "userdel", "groupadd", "groupdel",
    "mount", "umount",
    "crontab",
    "apt", "apt-get", "yum", "dnf", "pacman", "brew", "pip", "npm", "pnpm",
}


def _matches_forbidden(text: str, patterns: Iterable[str]) -> list[str]:
    """Return the patterns found in text."""
    found = []
    for p in patterns:
        if p in text:
            found.append(p)
    return found


# ── Validator ───────────────────────────────────────────────────────────

class PlanValidator:
    """Validates a Plan against structural and safety rules."""

    def __init__(self, project_ids: Iterable[str]):
        self.project_ids = set(project_ids)

    def validate(self, plan: Plan) -> ValidationResult:
        result = ValidationResult(valid=True)

        self._check_objective(plan, result)
        self._check_project_id(plan, result)
        self._check_steps(plan, result)
        self._check_dependencies(plan, result)
        self._check_verification(plan, result)
        self._check_estimated_complexity(plan, result)
        self._check_unsafe_commands(plan, result)

        return result

    # ── Field checks ─────────────────────────────────────────────────────

    def _check_objective(self, plan: Plan, result: ValidationResult) -> None:
        if not plan.objective or not plan.objective.strip():
            result.add_error(
                "EMPTY_OBJECTIVE",
                "Plan objective is required and must be non-empty.",
                field="objective",
            )
        elif len(plan.objective) < 5:
            result.add_warning(
                "SHORT_OBJECTIVE",
                "Objective is very short; consider expanding it.",
                field="objective",
            )

    def _check_project_id(self, plan: Plan, result: ValidationResult) -> None:
        if not plan.project_id or not plan.project_id.strip():
            result.add_error(
                "EMPTY_PROJECT_ID",
                "Plan project_id is required.",
                field="project_id",
            )
            return

        if self.project_ids and plan.project_id not in self.project_ids:
            result.add_error(
                "INVALID_PROJECT_ID",
                f"Project '{plan.project_id}' is not registered.",
                field="project_id",
            )

    def _check_estimated_complexity(self, plan: Plan, result: ValidationResult) -> None:
        valid = {c.value for c in PlanComplexity}
        if plan.estimated_complexity.value not in valid:
            result.add_warning(
                "UNKNOWN_COMPLEXITY",
                f"Estimated complexity '{plan.estimated_complexity.value}' is not a known value.",
                field="estimated_complexity",
            )

    # ── Step checks ─────────────────────────────────────────────────────

    def _check_steps(self, plan: Plan, result: ValidationResult) -> None:
        if not plan.steps:
            result.add_error(
                "NO_STEPS",
                "Plan must contain at least one step.",
                field="steps",
            )
            return

        seen_ids: set[str] = set()
        for i, step in enumerate(plan.steps):
            self._check_step(step, i, plan, result, seen_ids)

    def _check_step(
        self,
        step: PlanStep,
        index: int,
        plan: Plan,
        result: ValidationResult,
        seen_ids: set[str],
    ) -> None:
        prefix = f"steps[{index}]"

        # step_id
        if not step.step_id or not step.step_id.strip():
            result.add_error(
                "MISSING_STEP_ID",
                f"Step at index {index} is missing step_id.",
                field=f"{prefix}.step_id",
            )
        elif not is_valid_step_id(step.step_id):
            result.add_error(
                "INVALID_STEP_ID",
                f"Step id '{step.step_id}' contains invalid characters. "
                "Use letters, digits, hyphens, underscores.",
                field=f"{prefix}.step_id",
            )
        elif step.step_id in seen_ids:
            result.add_error(
                "DUPLICATE_STEP_ID",
                f"Step id '{step.step_id}' is used more than once.",
                field=f"{prefix}.step_id",
            )
        else:
            seen_ids.add(step.step_id)

        # title
        if not step.title or not step.title.strip():
            result.add_error(
                "MISSING_STEP_TITLE",
                f"Step '{step.step_id}' is missing title.",
                field=f"{prefix}.title",
            )

        # step_type
        if step.step_type not in ("shell", "python", "inspect"):
            result.add_error(
                "INVALID_STEP_TYPE",
                f"Step '{step.step_id}' has invalid step_type "
                f"'{step.step_type}'. Must be shell, python, or inspect.",
                field=f"{prefix}.step_type",
            )

        # type-specific checks
        if step.step_type == "shell" and not step.command:
            result.add_error(
                "MISSING_COMMAND",
                f"Shell step '{step.step_id}' must specify a command.",
                field=f"{prefix}.command",
            )
        if step.step_type == "python" and not step.command:
            result.add_error(
                "MISSING_MODULE",
                f"Python step '{step.step_id}' must specify a module.",
                field=f"{prefix}.command",
            )

    # ── Dependency checks ───────────────────────────────────────────────

    def _check_dependencies(self, plan: Plan, result: ValidationResult) -> None:
        all_ids = {s.step_id for s in plan.steps if s.step_id}
        for i, step in enumerate(plan.steps):
            for dep in step.dependencies:
                if not dep or not dep.strip():
                    result.add_error(
                        "EMPTY_DEPENDENCY",
                        f"Step '{step.step_id}' has empty dependency.",
                        field=f"steps[{i}].dependencies",
                    )
                elif dep not in all_ids:
                    result.add_error(
                        "UNKNOWN_DEPENDENCY",
                        f"Step '{step.step_id}' depends on unknown step_id '{dep}'.",
                        field=f"steps[{i}].dependencies",
                    )
                elif dep == step.step_id:
                    result.add_error(
                        "SELF_DEPENDENCY",
                        f"Step '{step.step_id}' depends on itself.",
                        field=f"steps[{i}].dependencies",
                    )

        # Cycle detection
        if self._has_cycle(plan):
            result.add_error(
                "CYCLIC_DEPENDENCIES",
                "Plan has cyclic step dependencies.",
                field="steps[].dependencies",
            )

    def _has_cycle(self, plan: Plan) -> bool:
        """DFS-based cycle detection."""
        graph: dict[str, list[str]] = {}
        for step in plan.steps:
            if step.step_id:
                graph[step.step_id] = step.dependencies

        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {n: WHITE for n in graph}

        def dfs(node: str) -> bool:
            if color.get(node) == GRAY:
                return True  # cycle
            if color.get(node) == BLACK:
                return False
            color[node] = GRAY
            for dep in graph.get(node, []):
                if dep in graph and dfs(dep):
                    return True
            color[node] = BLACK
            return False

        for node in graph:
            if color.get(node) == WHITE:
                if dfs(node):
                    return True
        return False

    # ── Verification checks ─────────────────────────────────────────────

    def _check_verification(self, plan: Plan, result: ValidationResult) -> None:
        if not plan.verification:
            result.add_warning(
                "NO_VERIFICATION_CRITERIA",
                "Plan defines no verification criteria. Plans without "
                "verification cannot be properly verified by the runner.",
                field="verification",
            )

        for i, vc in enumerate(plan.verification):
            if not vc.description or not vc.description.strip():
                result.add_warning(
                    "EMPTY_VERIFICATION_DESC",
                    f"Verification criterion at index {i} has no description.",
                    field=f"verification[{i}].description",
                )
            if vc.method not in ("manual", "typecheck", "test", "diff", "inspect", ""):
                result.add_warning(
                    "UNKNOWN_VERIFICATION_METHOD",
                    f"Verification method '{vc.method}' is not a known value.",
                    field=f"verification[{i}].method",
                )

    # ── Unsafe command checks ───────────────────────────────────────────

    def _check_unsafe_commands(self, plan: Plan, result: ValidationResult) -> None:
        for i, step in enumerate(plan.steps):
            prefix = f"steps[{i}]"

            if step.step_type in ("shell", "python"):
                # The first token is the command/module name
                cmd = step.command.strip()
                cmd_first = cmd.split()[0] if cmd else ""

                # Block forbidden commands
                if cmd_first in _FORBIDDEN_COMMANDS:
                    result.add_error(
                        "FORBIDDEN_COMMAND",
                        f"Step '{step.step_id}' uses forbidden command "
                        f"'{cmd_first}'.",
                        field=f"{prefix}.command",
                    )

                # Forbidden shell patterns in command or args
                full_text = " ".join([cmd] + list(step.arguments))
                forbidden = _matches_forbidden(full_text, _FORBIDDEN_SHELL_PATTERNS)
                if forbidden:
                    result.add_error(
                        "UNSAFE_SHELL_PATTERN",
                        f"Step '{step.step_id}' contains unsafe shell patterns: "
                        f"{forbidden}",
                        field=f"{prefix}.command",
                    )

                # Forbidden Python patterns
                if step.step_type == "python":
                    py_forbidden = _matches_forbidden(full_text, _FORBIDDEN_PYTHON_PATTERNS)
                    if py_forbidden:
                        result.add_error(
                            "UNSAFE_PYTHON_PATTERN",
                            f"Step '{step.step_id}' contains unsafe Python patterns: "
                            f"{py_forbidden}",
                            field=f"{prefix}.command",
                        )


# ── Convenience ─────────────────────────────────────────────────────────

def validate_plan(
    plan: Plan,
    project_ids: Iterable[str],
) -> ValidationResult:
    """One-shot validation function."""
    validator = PlanValidator(project_ids=project_ids)
    return validator.validate(plan)
