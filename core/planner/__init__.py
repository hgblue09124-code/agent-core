# core/planner/__init__.py
"""LLM Planner v0.2 — intent → structured plan.

Core principle:
    LLM = PLANNER
    TaskRunner = EXECUTOR
    Verification = AUTHORITY

LLM must NEVER execute commands directly.
"""

from core.planner.schema import (
    Plan,
    PlanStep,
    VerificationCriterion,
    PlanComplexity,
    ValidationError,
    ValidationResult,
)
from core.planner.planner import (
    Planner,
    PlannerProvider,
    MockPlannerProvider,
    LocalPlannerProvider,
    OpenRouterPlannerProvider,
    create_provider,
    load_provider_config,
    plan_to_task,
    PlanResult,
)
from core.planner.context import ContextBuilder, build_context
from core.planner.validator import PlanValidator, validate_plan

__all__ = [
    "Plan",
    "PlanStep",
    "VerificationCriterion",
    "PlanComplexity",
    "ValidationError",
    "ValidationResult",
    "Planner",
    "PlannerProvider",
    "MockPlannerProvider",
    "LocalPlannerProvider",
    "OpenRouterPlannerProvider",
    "create_provider",
    "load_provider_config",
    "plan_to_task",
    "PlanResult",
    "ContextBuilder",
    "build_context",
    "PlanValidator",
    "validate_plan",
]
