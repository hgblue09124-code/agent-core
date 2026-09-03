# core/experience/analyzer.py
"""Experience analyzer — computes metrics and patterns from experiences.

Provides deterministic aggregation:
    - success rate
    - failure rate
    - recovery rate
    - retry count
    - average duration
    - LLM calls
    - estimated token cost
    - verification success
    - knowledge reuse rate
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core.experience.schema import Experience


@dataclass
class ExperienceMetrics:
    """Aggregated metrics from experiences."""
    total: int = 0
    success_count: int = 0
    failure_count: int = 0
    recovery_count: int = 0
    total_llm_calls: int = 0
    total_tokens: int = 0
    total_duration: float = 0.0
    avg_duration: float = 0.0
    success_rate: float = 0.0
    failure_rate: float = 0.0
    recovery_rate: float = 0.0
    avg_llm_calls: float = 0.0
    avg_tokens: float = 0.0

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "recovery_count": self.recovery_count,
            "total_llm_calls": self.total_llm_calls,
            "total_tokens": self.total_tokens,
            "total_duration": self.total_duration,
            "avg_duration": self.avg_duration,
            "success_rate": self.success_rate,
            "failure_rate": self.failure_rate,
            "recovery_rate": self.recovery_rate,
            "avg_llm_calls": self.avg_llm_calls,
            "avg_tokens": self.avg_tokens,
        }


class ExperienceAnalyzer:
    """Analyzes experience records for patterns and metrics."""

    def analyze(self, experiences: list[Experience]) -> ExperienceMetrics:
        if not experiences:
            return ExperienceMetrics()

        total = len(experiences)
        success_count = sum(1 for e in experiences if e.success())
        failure_count = total - success_count

        # Recovery: had a failure but also had recovery text
        recovery_count = sum(
            1 for e in experiences
            if e.failure and e.recovery
        )

        total_llm_calls = sum(e.llm_calls for e in experiences)
        total_tokens = sum(e.estimated_tokens for e in experiences)
        total_duration = sum(e.duration for e in experiences)

        return ExperienceMetrics(
            total=total,
            success_count=success_count,
            failure_count=failure_count,
            recovery_count=recovery_count,
            total_llm_calls=total_llm_calls,
            total_tokens=total_tokens,
            total_duration=total_duration,
            avg_duration=total_duration / total if total > 0 else 0.0,
            success_rate=success_count / total if total > 0 else 0.0,
            failure_rate=failure_count / total if total > 0 else 0.0,
            recovery_rate=recovery_count / failure_count if failure_count > 0 else 0.0,
            avg_llm_calls=total_llm_calls / total if total > 0 else 0.0,
            avg_tokens=total_tokens / total if total > 0 else 0.0,
        )

    def by_domain(self, experiences: list[Experience]) -> dict[str, ExperienceMetrics]:
        """Group metrics by domain (extracted from goal/context)."""
        groups: dict[str, list[Experience]] = {}
        for e in experiences:
            # Simple domain extraction from goal
            domain = self._extract_domain(e.goal)
            groups.setdefault(domain, []).append(e)
        return {d: self.analyze(exps) for d, exps in groups.items()}

    def by_failure_category(self, experiences: list[Experience]) -> dict[str, list[Experience]]:
        """Group experiences by failure category."""
        from core.experience.recorder import FailureCategory
        groups: dict[str, list[Experience]] = {}
        for e in experiences:
            if e.failure:
                cat = FailureCategory.detect(e.failure)
            else:
                cat = "SUCCESS"
            groups.setdefault(cat, []).append(e)
        return groups

    def _extract_domain(self, goal: str) -> str:
        """Extract a simple domain from a goal string."""
        goal_lower = goal.lower()
        if "file" in goal_lower or "write" in goal_lower or "read" in goal_lower:
            return "file_io"
        if "test" in goal_lower or "pytest" in goal_lower:
            return "testing"
        if "build" in goal_lower or "compile" in goal_lower:
            return "build"
        if "network" in goal_lower or "http" in goal_lower or "api" in goal_lower:
            return "network"
        if "config" in goal_lower or "setup" in goal_lower:
            return "configuration"
        return "general"
