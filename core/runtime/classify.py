# core/runtime/classify.py
"""Cheap goal classification — skip the planner when the request is deterministic."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


_REMEMBER_RE = re.compile(
    r"^(?:please\s+)?(?:remember|ghi\s*nh[ớơ]|nh[ớơ])(?:\s+that)?\s+(.+)$",
    re.IGNORECASE | re.DOTALL,
)
_FORGET_RE = re.compile(
    r"^(?:please\s+)?(?:forget|qu[êe]n)(?:\s+(?:memory|the|key))?\s+(.+)$",
    re.IGNORECASE,
)
_FACT_IS_RE = re.compile(r"\bis\s+(.+)$", re.IGNORECASE)

CHEAP_STATUS_HINTS = (
    "status",
    "health",
    "version",
    "history",
    "ping",
    "smoke",
    "who are you",
    "your name",
    "cancel task",
)


@dataclass(frozen=True)
class GoalIntent:
    """Result of cheap classification. `cheap=True` means no planner call."""

    kind: str  # remember | forget | status | complex
    cheap: bool
    operation: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


def classify_goal(goal: str) -> GoalIntent:
    """Classify a user goal. Deterministic; no model, no I/O."""
    g = (goal or "").strip()
    if not g:
        return GoalIntent(kind="status", cheap=True, operation="echo", arguments={"text": ""}, reason="empty")

    m = _REMEMBER_RE.match(g)
    if m:
        content = m.group(1).strip().rstrip(".")
        key, value = split_fact(content)
        return GoalIntent(
            kind="remember",
            cheap=True,
            operation="remember",
            arguments={"key": key, "value": value, "content": content},
            reason="deterministic remember",
        )

    m = _FORGET_RE.match(g)
    if m:
        target = m.group(1).strip().rstrip(".")
        return GoalIntent(
            kind="forget",
            cheap=True,
            operation="forget",
            arguments={"query": target, "key": target},
            reason="deterministic forget",
        )

    gl = g.lower()
    if any(h in gl for h in CHEAP_STATUS_HINTS) and len(g.split()) <= 8:
        return GoalIntent(
            kind="status",
            cheap=True,
            operation="echo",
            arguments={"text": g},
            reason="deterministic status",
        )

    return GoalIntent(kind="complex", cheap=False, reason="needs plan")


def split_fact(content: str) -> tuple[str, str]:
    """Turn 'my favorite color is blue' into ('favorite color', 'blue')."""
    m = _FACT_IS_RE.search(content)
    if m:
        value = m.group(1).strip()
        key = content[: m.start()].strip()
        key = re.sub(r"^(?:that\s+)?(?:my|the)\s+", "", key, flags=re.IGNORECASE).strip() or content
        return key[:80], value[:400]
    if ":" in content:
        k, v = content.split(":", 1)
        return k.strip()[:80], v.strip()[:400]
    return content[:80], content[:400]
