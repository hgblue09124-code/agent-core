# core/learning/pipeline.py
"""Learning pipeline — converts Experience -> Lesson -> Candidate Strategy in Agent-Core."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from core.experience.schema import Experience
from core.experience.lesson import Lesson, LessonEngine
from core.learning.strategy import Strategy, StrategyStatus
from core.learning.store import StrategyStore


class LearningPipeline:
    """Explicit pipeline for converting experience observations into candidate strategies."""

    def __init__(
        self,
        strategy_store: Optional[StrategyStore] = None,
        lesson_engine: Optional[LessonEngine] = None,
    ):
        self.store = strategy_store or StrategyStore()
        self.lesson_engine = lesson_engine or LessonEngine()

    def process_experience(self, experience: Experience) -> Optional[Strategy]:
        """Convert a run Experience into a Lesson and a Candidate Strategy if applicable."""
        if not experience.run_id or not experience.goal:
            return None

        # 1. Extract Lesson
        lesson: Lesson = self.lesson_engine.extract(experience)
        if not lesson or not (lesson.title or lesson.description):
            return None

        # 2. Form Candidate Strategy
        now = datetime.now(timezone.utc).isoformat()
        strategy_id = f"STRAT-{uuid.uuid4().hex[:10]}"

        rule_summary = f"When goal matches '{experience.goal[:50]}', prefer verified plan sequence."
        if experience.outcome != "success":
            rule_summary = f"Avoid failure mode in goal '{experience.goal[:50]}': check prerequisites before execution."

        candidate = Strategy(
            strategy_id=strategy_id,
            name=f"Strategy from run {experience.run_id[:8]}",
            description=f"Derived from lesson: {(lesson.description or lesson.title)[:100]}",
            rule=rule_summary,
            applicable_context=experience.goal,
            expected_outcome=experience.outcome,
            evidence=[f"Experience {experience.run_id} outcome={experience.outcome}"],
            success_count=1 if experience.outcome == "success" else 0,
            failure_count=1 if experience.outcome != "success" else 0,
            confidence=0.35 if experience.outcome == "success" else 0.20,
            status=StrategyStatus.CANDIDATE.value,
            version=1,
            provenance=f"lesson-{lesson.lesson_id}",
            source_experiences=[experience.run_id],
            created_at=now,
            updated_at=now,
        )

        return self.store.create(candidate)
