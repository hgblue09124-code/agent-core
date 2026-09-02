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

Return a JSON object with exactly these fields:

{{
  "objective": "string — restate the user's goal",
  "assumptions": ["string — list of made assumptions"],
  "steps": [
    {{
      "step_id": "string — unique, e.g. 'step-1'",
      "title": "string — short label",
      "description": "string — what this step does",
      "step_type": "string — one of: shell | python | inspect",
      "dependencies": ["string — step_ids this depends on, e.g. ['step-1']"],
      "command": "string — command or module name",
      "arguments": ["string — arguments as separate items"],
      "expected_result": "string — what success looks like",
      "verify_contains": ["string — substrings that stdout SHOULD contain"],
      "verify_not_contains": ["string — substrings stdout MUST NOT contain"],
      "expect_exit_code": 0
    }}
  ],
  "verification": [
    {{
      "description": "string — what to check",
      "method": "string — one of: manual | typecheck | test | diff | inspect",
      "command": "string — optional command to run",
      "args": ["string"],
      "expect_exit_code": 0,
      "verify_contains": ["string"]
    }}
  ],
  "risks": ["string — potential issues"],
  "estimated_complexity": "string — one of: trivial | simple | moderate | complex",
  "notes": "string — any additional notes"
}}

IMPORTANT:
- Return ONLY the JSON. No markdown fences, no explanation, no preamble.
- All step_ids must be unique within the plan.
- All dependencies must reference existing step_ids.
- If a step has no dependencies, use an empty array.
- If verification criteria cannot be defined, return an empty array for "verification" and explain why in "notes".
"""


def build_system_prompt() -> str:
    return SYSTEM_PROLOGUE


def build_user_prompt(
    config: PromptConfig,
    context_text: str,
) -> str:
    """Build the full user prompt from objective + context."""
    parts = []

    parts.append(OBJECTIVE_BLOCK.format(objective=config.objective))
    parts.append(VERIFICATION_HINTS)
    parts.append(CONSTRAINTS_BLOCK)
    parts.append(CONTEXT_BLOCK.format(context=context_text))
    parts.append(OUTPUT_SCHEMA)

    return "\n\n".join(parts)


def build_full_prompt(
    config: PromptConfig,
    context_text: str,
) -> tuple[str, str]:
    """Build (system_prompt, user_prompt) tuple."""
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(config, context_text)
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
