# core/planner/context.py
"""Context Builder — assembles a token-budgeted prompt context.

Planner v0.2 — token-aware, no LLM.

Uses a word-based approximation for token count (1 token ≈ 0.75 words).
Since no tiktoken is available, this is labeled APPROXIMATE.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ── Token estimator ─────────────────────────────────────────────────────

# Rough approximation: 1 token ≈ 4 characters in English, or 0.75 words.
# We use a conservative estimate.
CHARS_PER_TOKEN = 4
WORDS_PER_TOKEN = 0.75


def estimate_tokens(text: str) -> int:
    """Estimate token count using character count ÷ CHARS_PER_TOKEN.

    This is a rough approximation. For production, replace with a real
    tokenizer (e.g. tiktoken). The value is labeled APPROXIMATE
    in all outputs.
    """
    return max(1, len(text) // CHARS_PER_TOKEN)


def estimate_tokens_words(text: str) -> int:
    """Estimate token count using word count ÷ WORDS_PER_TOKEN."""
    words = len(text.split())
    return max(1, int(words / WORDS_PER_TOKEN))


def estimate_tokens_combined(text: str) -> int:
    """Average of character and word estimates for better accuracy."""
    char_est = estimate_tokens(text)
    word_est = estimate_tokens_words(text)
    return (char_est + word_est) // 2


@dataclass
class ContextStats:
    """Statistics about a built context."""
    total_chars: int
    approx_tokens: int  # labeled APPROXIMATE
    documents_included: list[str]
    documents_excluded: list[str]
    total_files: int

    def summary(self) -> str:
        incl = ", ".join(self.documents_included) or "(none)"
        excl = ", ".join(self.documents_excluded) or "(none)"
        return (
            f"chars={self.total_chars}, "
            f"tokens≈{self.approx_tokens} (APPROXIMATE), "
            f"included={incl}, "
            f"excluded={excl}"
        )


# ── Context Document ────────────────────────────────────────────────────

@dataclass
class ContextDocument:
    """A document included in the planner context."""
    name: str          # e.g. "AGENT.md"
    role: str          # e.g. "agent_contract", "architecture"
    path: str         # absolute path
    content: str
    chars: int
    approx_tokens: int

    def truncated(self, max_chars: int) -> "ContextDocument":
        """Return a copy with truncated content."""
        if len(self.content) <= max_chars:
            return self
        return ContextDocument(
            name=self.name,
            role=self.role,
            path=self.path,
            content=self.content[:max_chars] + f"\n\n[... TRUNCATED — {len(self.content) - max_chars} chars omitted ...]",
            chars=max_chars,
            approx_tokens=self.approx_tokens,
        )


# ── Context Builder ────────────────────────────────────────────────────

DEFAULT_MAX_TOKENS = 4000   # conservative default budget


@dataclass
class ContextBuilder:
    """Assembles a project context within a token budget.

    Usage:
        cb = ContextBuilder(max_tokens=4000)
        cb.add_document("AGENT.md", "agent_contract", content)
        cb.add_document("ARCHITECTURE.md", "architecture", content)
        # ...
        ctx = cb.build()
        print(ctx.prompt_text)
        print(ctx.stats.summary())
    """
    max_tokens: int = DEFAULT_MAX_TOKENS
    documents: list[ContextDocument] = field(default_factory=list)
    _total_chars: int = field(default=0, repr=False)

    def add_document(
        self,
        name: str,
        role: str,
        path: str,
        content: str,
    ) -> bool:
        """Add a document if it fits the budget.

        Returns True if added, False if skipped (over budget).
        """
        chars = len(content)
        tokens = estimate_tokens_combined(content)

        # If adding this doc would exceed budget, skip it
        if self._total_chars + chars > self.max_tokens * CHARS_PER_TOKEN:
            return False

        self.documents.append(ContextDocument(
            name=name,
            role=role,
            path=path,
            content=content,
            chars=chars,
            approx_tokens=tokens,
        ))
        self._total_chars += chars
        return True

    def build(self) -> "PlannerContext":
        """Assemble the full context dict."""
        all_included = [d.name for d in self.documents]
        prompt_parts: list[str] = []

        for doc in self.documents:
            prompt_parts.append(
                f"## {doc.name} ({doc.role})\n"
                f"{doc.content}"
            )

        full_text = "\n\n---\n\n".join(prompt_parts)
        approx_tokens = estimate_tokens_combined(full_text)

        stats = ContextStats(
            total_chars=len(full_text),
            approx_tokens=approx_tokens,
            documents_included=all_included,
            documents_excluded=[],
            total_files=len(self.documents),
        )

        return PlannerContext(
            prompt_text=full_text,
            sections="\n\n---\n\n".join(
                f"### {d.role}\n{d.content}"
                for d in self.documents
            ),
            stats=stats,
            documents=self.documents,
        )


@dataclass
class PlannerContext:
    """The assembled context for the planner prompt."""
    prompt_text: str       # full text to include in the prompt
    sections: str          # structured sections
    stats: ContextStats
    documents: list[ContextDocument]


# ── Convenience factory ───────────────────────────────────────────────

def build_context(
    agent_contract: Optional[str],
    architecture: Optional[str],
    source_of_truth: Optional[str],
    project_metadata: Optional[dict] = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> PlannerContext:
    """Build a planner context from project document content.

    Args:
        agent_contract: content of AGENT.md (or None)
        architecture: content of ARCHITECTURE.md (or None)
        source_of_truth: content of source-of-truth.md (or None)
        project_metadata: dict with project_id, name, root_path, status
        max_tokens: token budget (approximate)
    """
    cb = ContextBuilder(max_tokens=max_tokens)

    if project_metadata:
        meta = [
            f"Project: {project_metadata.get('name', '?')}",
            f"ID: {project_metadata.get('project_id', '?')}",
            f"Root: {project_metadata.get('root_path', '?')}",
            f"Status: {project_metadata.get('status', '?')}",
        ]
        cb.add_document(
            name="project_metadata",
            role="metadata",
            path="(metadata)",
            content="\n".join(meta),
        )

    # Priority order: agent_contract, architecture, source_of_truth
    if agent_contract:
        cb.add_document(
            name="AGENT.md",
            role="agent_contract",
            path="AGENT.md",
            content=agent_contract,
        )

    if architecture:
        cb.add_document(
            name="ARCHITECTURE.md",
            role="architecture",
            path="ARCHITECTURE.md",
            content=architecture,
        )

    if source_of_truth:
        cb.add_document(
            name="source-of-truth.md",
            role="source_of_truth",
            path="docs/architecture/source-of-truth.md",
            content=source_of_truth,
        )

    ctx = cb.build()
    return ctx
