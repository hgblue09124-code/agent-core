# core/context/__init__.py
"""Context packing for Agent-Core — layered, budgeted, relevance-gated."""

from core.context.pack import (
    ContextPack,
    build_loop_pack,
    clip,
    compact_tool_output,
    needed_layers,
    select_relevant_slice,
)

__all__ = [
    "ContextPack",
    "build_loop_pack",
    "clip",
    "compact_tool_output",
    "needed_layers",
    "select_relevant_slice",
]
