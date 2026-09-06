# core/planner/prompt.py
"""Planner v0.2 — deterministic prompt builder.

Produces a structured prompt that tells the LLM:
- its role (PLANNER, not EXECUTOR)
- what context it has
- what output schema is required
- what constraints apply
"""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass
class PromptConfig:
    """Configuration for the planner prompt."""
    project_id: str
    project_name: str
    objective: str
    allow_shell: bool = True
    allow_python: bool = True
    allow_inspect: bool = True
    max_steps: int = 10


SYSTEM_PROLOGUE = """\
You are a PLANNING COMPONENT for an autonomous task system.
You do NOT execute commands. You do NOT modify files.
You only produce a structured plan as JSON.

Your output will be validated. Malformed plans will be rejected.
Return ONLY valid JSON matching the required schema. Do not add commentary.\
"""

CONSTRAINTS_BLOCK = """\
## Constraints

1. NEVER suggest eval(), exec(), or dynamic code generation.
2. Every step must be explicitly typed: "shell", "python", or "inspect".
3. Shell commands must use explicit arguments (no shell=True injection).
4. The user must be able to verify the plan independently.
5. Plans that require modifying existing gameplay logic MUST be marked as risky.
6. Do not suggest steps that would destroy data.
7. If the objective is unclear, make reasonable assumptions and list them in "assumptions".\
"""

VERIFICATION_HINTS = """\
## Verification

Define 2-5 concrete verification criteria for the plan:
- Each criterion must describe WHAT to verify, not HOW (the execution layer decides how).
- Examples of good criteria: "typecheck passes", "no unrelated files modified",
  "generated docs reflect actual code structure".
- Bad criterion: "run the test suite" (too vague).
- A plan without verification criteria will be REJECTED.\
"""

OBJECTIVE_BLOCK = """\
## User Objective

{objective}\
"""

CONTEXT_BLOCK = """\
## Project Context

The following documents were extracted from the project.
They are the SOURCE OF TRUTH for what the system looks like.

{context}\
"""

OUTPUT_SCHEMA = """\
## Required Output Schema

Return ONLY JSON (no markdown fences) with keys:
objective, assumptions, steps, verification, risks, estimated_complexity, notes.

Each step: step_id, title, description, step_type (shell|python|inspect),
dependencies, command, arguments, expected_result, verify_contains,
verify_not_contains, expect_exit_code.

Each verification: description, method (manual|typecheck|test|diff|inspect),
command, args, expect_exit_code, verify_contains.
"""


def build_system_prompt() -> str:
    # Static prefix: constraints live here so the user prompt is per-task only.
    return SYSTEM_PROLOGUE + "\n\n" + CONSTRAINTS_BLOCK


def build_user_prompt(
    config: PromptConfig,
    context_text: str,
    extra_context: str = "",
) -> str:
    """Build the user prompt from objective + selected context."""
    parts = [
        OBJECTIVE_BLOCK.format(objective=config.objective),
        VERIFICATION_HINTS,
    ]
    extra = (extra_context or "").strip()
    if extra:
        parts.append("## Retrieved Context\n\n" + extra)
    parts.append(CONTEXT_BLOCK.format(context=context_text))
    parts.append(OUTPUT_SCHEMA)
    return "\n\n".join(parts)


def build_full_prompt(
    config: PromptConfig,
    context_text: str,
    extra_context: str = "",
) -> tuple[str, str]:
    """Build (system_prompt, user_prompt) tuple."""
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(config, context_text, extra_context=extra_context)
    return system_prompt, user_prompt


# ── Raw response parser ─────────────────────────────────────────────────

def strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` fences if present."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Remove opening ```json or ```
        if lines[0].startswith("```"):
            lines = lines[1:]
        # Remove closing ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def parse_llm_response(raw: str) -> dict:
    """Parse LLM raw text into a dict. Raises ValueError on failure."""
    cleaned = strip_markdown_fences(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"LLM response is not valid JSON: {exc}\n"
            f"Raw (first 200 chars): {cleaned[:200]!r}"
        ) from exc
