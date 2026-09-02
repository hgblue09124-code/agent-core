# core/runtime/config.py
"""Runtime configuration — token/runtime budgets, internet policy."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class RuntimeConfig:
    """Budget & policy knobs for autonomous runs.

    All fields can be overridden by env vars, but defaults are sane.
    """
    max_llm_calls: int = 100
    max_token_budget: int = 100_000
    max_plan_refinements: int = 2
    max_retries: int = 3
    max_runtime_seconds: int = 28800  # 8 hours
    internet_policy: str = "off"      # off | on | required

    @classmethod
    def from_env(cls) -> "RuntimeConfig":
        """Build config from env vars, falling back to defaults."""
        return cls(
            max_llm_calls=int(os.environ.get("AGENTCORE_RUNTIME_MAX_LLM_CALLS", 100)),
            max_token_budget=int(os.environ.get("AGENTCORE_RUNTIME_MAX_TOKEN_BUDGET", 100_000)),
            max_plan_refinements=int(os.environ.get("AGENTCORE_RUNTIME_MAX_REFINEMENTS", 2)),
            max_retries=int(os.environ.get("AGENTCORE_RUNTIME_MAX_RETRIES", 3)),
            max_runtime_seconds=int(os.environ.get("AGENTCORE_RUNTIME_MAX_SECONDS", 28800)),
            internet_policy=os.environ.get("AGENTCORE_RUNTIME_INTERNET", "off").lower(),
        )
