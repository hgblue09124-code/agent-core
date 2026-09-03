# core/kernel/context.py
"""Kernel context — collects context for planning from existing subsystems."""

from __future__ import annotations

from typing import Optional

from core.kernel.schema import KernelContext


class KernelContextBuilder:
    """Build planning context from knowledge + experience.

    This is the knowledge → planning integration point.
    """

    def build(self, goal: str, knowledge_ids: list[str],
              knowledge_engine=None) -> dict:
        """Build a context dict for the LLM planner.

        Args:
            goal: the task goal
            knowledge_ids: primitive IDs retrieved from knowledge engine
            knowledge_engine: optional KnowledgeEngine for enrichment
        """
        context = {
            "goal": goal,
            "knowledge_primitives": [],
            "experience_hints": [],
            "policy_notes": [],
        }

        # Enrich with knowledge primitives
        if knowledge_engine:
            for kid in knowledge_ids:
                prim = knowledge_engine.get_primitive(kid)
                if prim:
                    context["knowledge_primitives"].append({
                        "id": prim.id,
                        "domain": prim.domain,
                        "concept": prim.concept,
                        "when_to_use": prim.when_to_use,
                        "implementation_pattern": prim.implementation_pattern,
                        "failure_modes": prim.failure_modes,
                        "verification_method": prim.verification_method,
                        "confidence": prim.confidence,
                        "status": prim.status,
                    })
                    if prim.failure_modes:
                        context["policy_notes"].append(
                            f"[{prim.domain}] known failure modes: {', '.join(prim.failure_modes[:2])}"
                        )

        return context
