# core/experience/lesson.py
"""Lesson Engine v0.8 — extracts lessons from experience records.

Pipeline:
    Experience
        ↓
    Pattern extraction
        ↓
    Candidate lesson
        ↓
    Validation
        ↓
    Evidence check
        ↓
    Knowledge candidate

Rules:
    - A single anecdotal experience must NOT automatically become high-confidence knowledge.
    - Track evidence count.
    - Support: first observation, repeated observation, contradictory observation, resolved observation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, List

from core.experience.schema import Experience
from core.experience.recorder import FailureCategory
from core.knowledge.schema import KnowledgeStatus, SourceType, Primitive, generate_primitive_id


# ── Lesson types ──────────────────────────────────────────────────────

class LessonType(str):
    FIRST_OBSERVATION = "FIRST_OBSERVATION"
    REPEATED_OBSERVATION = "REPEATED_OBSERVATION"
    CONTRADICTORY_OBSERVATION = "CONTRADICTORY_OBSERVATION"
    RESOLVED_OBSERVATION = "RESOLVED_OBSERVATION"


# ── Lesson ────────────────────────────────────────────────────────────

@dataclass
class Lesson:
    """A lesson extracted from experience.

    Lessons are NOT automatically promoted to knowledge. They require
    validation and evidence before they can influence future runs.
    """
    lesson_id: str
    title: str
    description: str
    lesson_type: str  # LessonType value
    source_experience_id: str
    evidence_count: int = 0
    contradiction_ids: list[str] = field(default_factory=list)
    resolved: bool = False
    confidence: float = 0.0
    created_at: str = ""
    schema_version: int = 1

    def to_dict(self) -> dict:
        return {
            "lesson_id": self.lesson_id,
            "title": self.title,
            "description": self.description,
            "lesson_type": self.lesson_type,
            "source_experience_id": self.source_experience_id,
            "evidence_count": self.evidence_count,
            "contradiction_ids": list(self.contradiction_ids),
            "resolved": self.resolved,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Lesson":
        return cls(
            lesson_id=d["lesson_id"],
            title=d.get("title", ""),
            description=d.get("description", ""),
            lesson_type=d.get("lesson_type", LessonType.FIRST_OBSERVATION),
            source_experience_id=d.get("source_experience_id", ""),
            evidence_count=int(d.get("evidence_count", 0)),
            contradiction_ids=list(d.get("contradiction_ids", [])),
            resolved=bool(d.get("resolved", False)),
            confidence=float(d.get("confidence", 0.0)),
            created_at=d.get("created_at", ""),
            schema_version=int(d.get("schema_version", 1)),
        )

    # ── Helpers ──────────────────────────────────────────────────────

    def success_rate(self) -> float:
        if self.evidence_count == 0:
            return 0.0
        return 1.0  # lessons are treated as verified until contradicted

    def is_contradicted_by(self, other: "Lesson") -> bool:
        """Check if this lesson is contradicted by another."""
        return other.lesson_id in self.contradiction_ids

    def add_contradiction(self, other_id: str) -> None:
        if other_id not in self.contradiction_ids:
            self.contradiction_ids.append(other_id)


# ── Lesson Engine ─────────────────────────────────────────────────────

class LessonEngine:
    """Extracts lessons from experience records.

    Rules:
        1. A single experience → FIRST_OBSERVATION lesson (low confidence)
        2. Same lesson extracted again → REPEATED_OBSERVATION (confidence +1)
        3. Same concept but opposite outcome → CONTRADICTORY_OBSERVATION
        4. Contradiction resolved by new evidence → RESOLVED_OBSERVATION
    """

    def __init__(self):
        self._lessons: dict[str, Lesson] = {}  # lesson_id -> Lesson
        self._evidence_index: dict[str, list[str]] = {}  # concept -> [lesson_ids]

    def extract(self, experience: Experience) -> Lesson:
        """Extract a lesson from a single experience.

        Returns a new Lesson with FIRST_OBSERVATION type and low confidence.
        """
        # Determine concept from experience
        concept = self._extract_concept(experience)
        title = self._extract_title(experience)
        description = self._extract_description(experience)

        lesson_id = f"L-{experience.run_id}-{concept[:20]}"
        lesson = Lesson(
            lesson_id=lesson_id,
            title=title,
            description=description,
            lesson_type=LessonType.FIRST_OBSERVATION,
            source_experience_id=experience.run_id,
            evidence_count=1,
            confidence=0.2,  # low confidence for first observation
            created_at=experience.created_at,
        )

        # Store
        self._lessons[lesson_id] = lesson
        self._evidence_index.setdefault(concept, []).append(lesson_id)
        return lesson

    def _extract_concept(self, exp: Experience) -> str:
        """Extract a concise concept from experience."""
        # Simple heuristic: first significant word after action
        text = exp.action.lower()
        # Remove common words
        stop = {"the", "a", "an", "to", "of", "in", "for", "on", "with"}
        words = [w for w in text.split() if w not in stop and len(w) > 2]
        if words:
            return words[0]
        return "general"

    def _extract_title(self, exp: Experience) -> str:
        """Extract a short title."""
        return exp.action[:60] if exp.action else "unknown action"

    def _extract_description(self, exp: Experience) -> str:
        """Extract a description from observation."""
        if exp.observation:
            return exp.observation[:120]
        return exp.outcome[:120] if exp.outcome else ""

    def record_observation(self, experience: Experience,
                          concept: str,
                          title: str,
                          description: str) -> Lesson:
        """Record an observation and update existing lesson or create new one."""
        lesson_id = f"L-{experience.run_id}-{concept[:20]}"
        if lesson_id in self._lessons:
            lesson = self._lessons[lesson_id]
            # Increment evidence count
            lesson.evidence_count += 1
            # Update confidence based on count
            lesson.confidence = min(1.0, 0.2 + 0.1 * min(lesson.evidence_count, 5))
            lesson.description = description
            return lesson
        else:
            lesson = Lesson(
                lesson_id=lesson_id,
                title=title,
                description=description,
                lesson_type=LessonType.FIRST_OBSERVATION,
                source_experience_id=experience.run_id,
                evidence_count=1,
                confidence=0.2,
                created_at=experience.created_at,
            )
            self._lessons[lesson_id] = lesson
            self._evidence_index.setdefault(concept, []).append(lesson_id)
            return lesson

    def detect_contradiction(self,
                           lesson_id: str,
                           new_lesson_id: str) -> bool:
        """Detect if two lessons contradict each other."""
        if lesson_id not in self._lessons or new_lesson_id not in self._lessons:
            return False
        l1 = self._lessons[lesson_id]
        l2 = self._lessons[new_lesson_id]
        # Check if they have opposite outcomes
        # Simple heuristic: different lesson types or different descriptions
        if l1.lesson_type != l2.lesson_type:
            l1.add_contradiction(new_lesson_id)
            l2.add_contradiction(lesson_id)
            return True
        return False

    def resolve_contradiction(self,
                              lesson_id: str,
                              resolution_evidence: str) -> Lesson:
        """Mark a contradiction as resolved."""
        if lesson_id not in self._lessons:
            return None
        lesson = self._lessons[lesson_id]
        lesson.resolved = True
        lesson.confidence = min(1.0, lesson.confidence + 0.2)
        lesson.evidence_count += 1
        return lesson

    def get_lesson(self, lesson_id: str) -> Optional[Lesson]:
        return self._lessons.get(lesson_id)

    def get_lessons_by_concept(self, concept: str) -> list[Lesson]:
        ids = self._evidence_index.get(concept, [])
        return [self._lessons[lid] for lid in ids if lid in self._lessons]

    def lessons_summary(self) -> dict:
        """Summary of all lessons."""
        total = len(self._lessons)
        by_type: dict[str, int] = {}
        for lesson in self._lessons.values():
            t = lesson.lesson_type
            by_type[t] = by_type.get(t, 0) + 1
        return {
            "total": total,
            "by_type": by_type,
            "avg_confidence": sum(l.confidence for l in self._lessons.values()) / total if total else 0.0,
        }