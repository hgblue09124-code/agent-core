# core/philosophy/__init__.py
"""Agent Philosophy Package — soft behavioral tendencies and human teaching feedback."""

from core.philosophy.schema import (
    PhilosophyStatus,
    TeachingType,
    EvolutionRecord,
    PhilosophyTendency,
)
from core.philosophy.store import PhilosophyStore, PhilosophyStoreError
from core.philosophy.engine import PhilosophyEngine, PhilosophyPrecedenceError

__all__ = [
    "PhilosophyStatus",
    "TeachingType",
    "EvolutionRecord",
    "PhilosophyTendency",
    "PhilosophyStore",
    "PhilosophyStoreError",
    "PhilosophyEngine",
    "PhilosophyPrecedenceError",
]
