# core/__init__.py
"""Agent-Core v0.1.0-beta Developer Preview Package."""

from core.agent import Agent, AgentRunResult
from core.kernel.kernel import Kernel, KernelResult
from core.experience.schema import Experience
from core.philosophy.engine import PhilosophyEngine
from core.philosophy.schema import PhilosophyTendency

__version__ = "0.1.0-beta"

__all__ = [
    "__version__",
    "Agent",
    "AgentRunResult",
    "Kernel",
    "KernelResult",
    "Experience",
    "PhilosophyEngine",
    "PhilosophyTendency",
]
