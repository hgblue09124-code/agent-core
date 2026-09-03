# core/experience/engine.py
"""ExperienceEngine — high-level orchestrator for the experience subsystem.

Combines: store, recorder, normalizer, analyzer, lesson, learner, promotion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core.experience.schema import Experience
from core.experience.store import ExperienceStore
from core.experience.recorder import ExperienceRecorder, FailureCategory
from core.experience.normalizer import normalize_observation, NormalizedObservation
from core.experience.analyzer import ExperienceAnalyzer, ExperienceMetrics
from core.experience.lesson import Lesson, LessonEngine
from core.experience.learner import ExperienceLearner, KnowledgeCandidate
from core.experience.promotion import ExperiencePromoter, PromotionResult


@dataclass
class ExperienceEngineStats:
    total_experiences: int = 0
    total_lessons: int = 0
    total_candidates: int = 0
    total_promoted: int = 0
    metrics: ExperienceMetrics = field(default_factory=ExperienceMetrics)


class ExperienceEngine:
    """Public API for the experience subsystem.

    Usage:
        engine = ExperienceEngine(store_dir="/path/to/experience")
        exp = engine.record_from_runtime(run_state, task_outcomes)
        engine.store_experience(exp)
        lesson = engine.extract_lesson(exp)
        candidates = engine.learn_from_experiences([exp])
        promotions = engine.promote_candidates(candidates)
    """

    def __init__(self, store_dir: Optional[str] = None):
        self.store = ExperienceStore(store_dir)
        self.recorder = ExperienceRecorder()
        self.normalizer = None  # not needed as separate instance
        self.analyzer = ExperienceAnalyzer()
        self.lesson_engine = LessonEngine()
        self.learner = ExperienceLearner(self.analyzer)
        self.promoter = ExperiencePromoter(self._get_knowledge_engine())

        # Load existing experiences
        self._experiences: dict[str, Experience] = {}
        for exp in self.store.list_all():
            self._experiences[exp.run_id] = exp

    def _get_knowledge_engine(self):
        """Lazy import to avoid circular dependency."""
        from core.knowledge.engine import KnowledgeEngine
        return KnowledgeEngine()

    # ── Recording ─────────────────────────────────────────────────────

    def record_from_runtime(self, run_state: dict,
                           task_outcomes: list[dict]) -> Experience:
        """Create an Experience from RuntimeEngine output."""
        from core.experience.recorder import record_from_run_state
        return record_from_run_state(run_state, task_outcomes)

    def record_experience(self, exp: Experience) -> Experience:
        """Record an experience (append-only)."""
        if not exp.run_id:
            raise ValueError("run_id is required")
        if self.store.exists(exp.run_id):
            raise ValueError(f"Experience already exists: {exp.run_id}")
        exp = self.store.create(exp)
        self._experiences[exp.run_id] = exp
        return exp

    def get_experience(self, run_id: str) -> Optional[Experience]:
        return self.store.get(run_id)

    def list_experiences(self) -> list[Experience]:
        return self.store.list_all()

    # ── Normalization ────────────────────────────────────────────────

    def normalize_observation(self, raw: str) -> NormalizedObservation:
        return normalize_observation(raw)

    def normalize_observations(self, raw_list: list[str]) -> list[NormalizedObservation]:
        return normalize_observations(raw_list)

    # ── Analysis ─────────────────────────────────────────────────────

    def analyze(self, experiences: Optional[list[Experience]] = None) -> ExperienceMetrics:
        if experiences is None:
            experiences = self.list_experiences()
        return self.analyzer.analyze(experiences)

    def by_failure_category(self, experiences: Optional[list[Experience]] = None) -> dict[str, list[Experience]]:
        if experiences is None:
            experiences = self.list_experiences()
        return self.analyzer.by_failure_category(experiences)

    # ── Lessons ──────────────────────────────────────────────────────

    def extract_lesson(self, experience: Experience) -> Lesson:
        return self.lesson_engine.extract(experience)

    def extract_lessons(self, experiences: list[Experience]) -> list[Lesson]:
        return [self.extract_lesson(e) for e in experiences]

    def get_lesson(self, lesson_id: str) -> Optional[Lesson]:
        return self.lesson_engine.get_lesson(lesson_id)

    # ── Learning ─────────────────────────────────────────────────────

    def learn(self, experiences: Optional[list[Experience]] = None) -> list[KnowledgeCandidate]:
        if experiences is None:
            experiences = self.list_experiences()
        return self.learner.learn(experiences)

    def get_candidates(self) -> list[KnowledgeCandidate]:
        return self.learner.get_candidates()

    def reject_candidate(self, candidate: KnowledgeCandidate, reason: str) -> None:
        self.learner.reject_candidate(candidate, reason)

    # ── Promotion ─────────────────────────────────────────────────────

    def promote(self, experiences: Optional[list[Experience]] = None) -> list[PromotionResult]:
        if experiences is None:
            experiences = self.list_experiences()
        return self.promoter.promote(experiences)

    def get_promotion_results(self) -> list[PromotionResult]:
        return self.promoter.get_results()

    # ── Stats ────────────────────────────────────────────────────────

    def stats(self) -> ExperienceEngineStats:
        experiences = self.list_experiences()
        lessons = [self.extract_lesson(e) for e in experiences]
        candidates = self.learn(experiences)
        promotions = self.promote(experiences)
        metrics = self.analyze(experiences)

        return ExperienceEngineStats(
            total_experiences=len(experiences),
            total_lessons=len(lessons),
            total_candidates=len(candidates),
            total_promoted=sum(1 for p in promotions if p.promoted),
            metrics=metrics,
        )