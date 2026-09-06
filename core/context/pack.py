# core/context/pack.py
"""Layered context packer — selects and clips what the model is allowed to see.

Layers:
    system          static role (owned by the caller / planner prompt)
    persistent      identity / long-lived prefs, only if the task needs them
    session         compact run summary, not full observation history
    current_task    goal + current action
    retrieved       top-k memory / vault / knowledge / strategy snippets
    tool_output     last observation only, truncated

Default policy: send current_task. Optional layers are gated by the goal so a
GitHub list-issues task does not receive identity + AGENT.md + philosophy.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional


# Approximate token budget per layer (1 token ≈ 4 chars).
LAYER_CHAR_BUDGET = {
    "persistent": 240,
    "session": 400,
    "current_task": 600,
    "retrieved": 1600,
    "tool_output": 1500,
}

MAX_TOOL_OUTPUT_CHARS = 1500
TOOL_OUTPUT_TAIL_CHARS = 200

_IDENTITY_HINTS = (
    "who are you",
    "your name",
    "identity",
    "remember me",
    "my preference",
    "personal",
    "about yourself",
)
_PROJECT_HINTS = (
    "architecture",
    "inspect",
    "codebase",
    "source",
    "refactor",
    "file",
    "module",
    "plan",
    "implement",
    "kernel",
)
_PREF_HINTS = (
    "preference",
    "favorite",
    "theme",
    "dark mode",
    "giao diện",
    "ui theo",
)
_TOKEN_RE = re.compile(r"[a-z0-9_]+")


def estimate_chars_budget(tokens: int) -> int:
    return max(0, tokens * 4)


def clip(text: Any, max_chars: int) -> str:
    """Clip a value to max_chars, preserving a readable suffix marker."""
    if text is None:
        return ""
    s = text if isinstance(text, str) else str(text)
    if max_chars <= 0:
        return ""
    if len(s) <= max_chars:
        return s
    keep = max(0, max_chars - 48)
    omitted = len(s) - keep
    return s[:keep].rstrip() + f"\n[... truncated {omitted} chars ...]"


def compact_tool_output(output: Any, max_chars: int = MAX_TOOL_OUTPUT_CHARS) -> str:
    """Keep the head of a tool result plus a short tail so errors at the end survive."""
    if output is None:
        return ""
    s = output if isinstance(output, str) else str(output)
    if len(s) <= max_chars:
        return s
    tail = TOOL_OUTPUT_TAIL_CHARS
    head = max_chars - tail - 40
    if head < 80:
        return clip(s, max_chars)
    omitted = len(s) - head - tail
    return (
        s[:head].rstrip()
        + f"\n[... truncated {omitted} chars ...]\n"
        + s[-tail:].lstrip()
    )


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def needed_layers(goal: str, *, has_session: bool = False, has_tool_output: bool = False) -> set[str]:
    """Return which optional layers belong in the next prompt.

    `current_task` is always included. Other layers are opt-in.
    """
    layers = {"current_task"}
    g = (goal or "").lower()
    if any(h in g for h in _IDENTITY_HINTS):
        layers.add("persistent")
    if any(h in g for h in _PREF_HINTS):
        layers.add("persistent")
        layers.add("retrieved")
    if any(h in g for h in _PROJECT_HINTS):
        layers.add("retrieved")
    # Capability / inspect tasks still benefit from a tiny retrieved slice
    # only when the caller already ranked hits — packing is cheap if empty.
    if has_session:
        layers.add("session")
    if has_tool_output:
        layers.add("tool_output")
    return layers


def layer_hash(text: str) -> str:
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


@dataclass
class ContextPack:
    """Compact, serializable context for one planner / loop turn."""

    current_task: str = ""
    persistent: str = ""
    session: str = ""
    retrieved: str = ""
    tool_output: str = ""
    last_sent_hashes: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "current_task": self.current_task,
            "persistent": self.persistent,
            "session": self.session,
            "retrieved": self.retrieved,
            "tool_output": self.tool_output,
            "last_sent_hashes": dict(self.last_sent_hashes),
        }

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "ContextPack":
        d = d or {}
        return cls(
            current_task=d.get("current_task", ""),
            persistent=d.get("persistent", ""),
            session=d.get("session", ""),
            retrieved=d.get("retrieved", ""),
            tool_output=d.get("tool_output", ""),
            last_sent_hashes=dict(d.get("last_sent_hashes") or {}),
        )

    def select_and_render(
        self,
        goal: str,
        *,
        has_session: Optional[bool] = None,
        dedup: bool = True,
    ) -> str:
        """Render only the layers this goal needs. Skip layers the model already got."""
        session_on = self.session if (has_session if has_session is not None else bool(self.session)) else ""
        layers = needed_layers(
            goal,
            has_session=bool(session_on),
            has_tool_output=bool(self.tool_output),
        )
        parts: list[str] = []
        sent: dict[str, str] = dict(self.last_sent_hashes)

        def _maybe(name: str, title: str, body: str) -> None:
            body = (body or "").strip()
            if not body or name not in layers:
                return
            body = clip(body, LAYER_CHAR_BUDGET.get(name, 800))
            h = layer_hash(body)
            if dedup and sent.get(name) == h:
                return
            parts.append(f"### {title}\n{body}")
            sent[name] = h

        _maybe("current_task", "Current task", self.current_task)
        _maybe("persistent", "Persistent memory", self.persistent)
        _maybe("session", "Session", session_on)
        _maybe("retrieved", "Retrieved", self.retrieved)
        _maybe("tool_output", "Last tool output", self.tool_output)

        self.last_sent_hashes = sent
        return "\n\n".join(parts)


def _one_line(text: Any, max_chars: int = 200) -> str:
    s = "" if text is None else str(text)
    s = " ".join(s.split())
    return clip(s, max_chars)


def _strategy_line(strat: Any) -> str:
    rule = getattr(strat, "rule", None) or getattr(strat, "title", None) or str(strat)
    status = getattr(strat, "status", "")
    sid = getattr(strat, "strategy_id", "")
    prefix = f"{sid} [{status}] " if sid else ""
    return _one_line(prefix + str(rule), 180)


def build_loop_pack(
    goal: str,
    *,
    identity: Any = None,
    memories: Optional[Iterable[Any]] = None,
    vault_items: Optional[Iterable[Any]] = None,
    strategies: Optional[Iterable[Any]] = None,
    knowledge_summaries: Optional[Iterable[Any]] = None,
    session_summary: str = "",
    last_tool_output: Any = None,
) -> ContextPack:
    """Assemble a pack from already-retrieved objects. Does not re-query stores."""
    identity_text = ""
    if identity is not None:
        content = getattr(identity, "content", identity)
        identity_text = _one_line(content, LAYER_CHAR_BUDGET["persistent"])

    retrieved_bits: list[str] = []
    for mem in memories or []:
        content = getattr(mem, "content", mem)
        retrieved_bits.append("- mem: " + _one_line(content, 200))
    for item in vault_items or []:
        if isinstance(item, dict):
            retrieved_bits.append("- vault: " + _one_line(item.get("data", item), 200))
        else:
            retrieved_bits.append("- vault: " + _one_line(item, 200))
    for strat in strategies or []:
        retrieved_bits.append("- strategy: " + _strategy_line(strat))
    for prim in knowledge_summaries or []:
        if isinstance(prim, dict):
            concept = prim.get("concept") or prim.get("id") or ""
            when = prim.get("when_to_use") or ""
            retrieved_bits.append("- knowledge: " + _one_line(f"{concept} — {when}", 200))
        else:
            retrieved_bits.append("- knowledge: " + _one_line(prim, 200))

    retrieved = "\n".join(retrieved_bits[:8])
    retrieved = clip(retrieved, LAYER_CHAR_BUDGET["retrieved"])

    # Persistent identity is stored always (cheap) but only *rendered* when needed.
    return ContextPack(
        current_task=clip(goal, LAYER_CHAR_BUDGET["current_task"]),
        persistent=identity_text,
        session=clip(session_summary, LAYER_CHAR_BUDGET["session"]),
        retrieved=retrieved,
        tool_output=compact_tool_output(last_tool_output) if last_tool_output else "",
    )


def select_relevant_slice(content: str, query: str, max_chars: int) -> str:
    """Pick the most query-overlapping windows of a document, then clip to budget."""
    if not content or max_chars <= 0:
        return ""
    if len(content) <= max_chars:
        return content
    qtok = _tokens(query)
    if not qtok:
        return clip(content, max_chars)

    # Split on markdown headings / blank lines into coarse sections.
    sections = re.split(r"\n(?=#{1,3}\s)|\n{2,}", content)
    scored: list[tuple[int, int, str]] = []
    for i, sec in enumerate(sections):
        if not sec.strip():
            continue
        overlap = len(qtok & _tokens(sec))
        scored.append((overlap, -i, sec))
    scored.sort(reverse=True)

    chosen: list[str] = []
    used = 0
    # Always keep a short head so the document identity is not lost.
    head = content[: min(400, max_chars // 4)]
    chosen.append(head)
    used += len(head)
    for overlap, _neg_i, sec in scored:
        if overlap <= 0:
            break
        if used >= max_chars:
            break
        if sec in head:
            continue
        piece = clip(sec.strip(), max_chars - used)
        chosen.append(piece)
        used += len(piece)
    text = "\n\n".join(chosen)
    return clip(text, max_chars)
