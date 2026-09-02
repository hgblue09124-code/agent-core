# core/config/manager.py
"""Config Manager v0.5 — reads and validates provider config from environment.

Does NOT call any API. Does NOT persist secrets.
All secrets stay in memory only.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional


# ── Validated config dataclass ─────────────────────────────────────────

@dataclass
class ProviderConfig:
    """Validated provider configuration. Secrets never printed/logged."""
    provider: str           # "openai" | "openrouter" | "local" | "mock"
    api_key: str           # secret, in-memory only
    base_url: str
    model: str
    ready: bool
    error: Optional[str]   # None when ready=True


# ── Config Manager ──────────────────────────────────────────────────────

_PROVIDER_ENVS = {
    "openai": {
        "key": "OPENAI_API_KEY",
        "base_url": "OPENAI_BASE_URL",
        "model": "OPENAI_MODEL",
        "default_base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
    },
    "openrouter": {
        "key": "AGENTCORE_PLANNER_API_KEY",
        "base_url": "AGENTCORE_PLANNER_BASE_URL",
        "model": "AGENTCORE_PLANNER_MODEL",
        "default_base_url": "https://openrouter.ai/api/v1",
        "default_model": "openai/gpt-4o",
    },
    "local": {
        "key": "AGENTCORE_PLANNER_API_KEY",
        "base_url": "AGENTCORE_PLANNER_BASE_URL",
        "model": "AGENTCORE_PLANNER_MODEL",
        "default_base_url": "http://localhost:11434",
        "default_model": "llama3",
    },
    "mock": {},
}

_URL_PATTERN = re.compile(r"^https?://[^\s]+$")


class ConfigManager:
    """Reads and validates provider config from environment variables.

    Does NOT call any API. Does NOT persist secrets.
    All secrets stay in memory only.
    """

    def __init__(self):
        # Detect provider
        self._provider = self._detect_provider()

        # Read and resolve values
        envs = _PROVIDER_ENVS.get(self._provider, {})

        key_env = envs.get("key", "")
        self._api_key = os.environ.get(key_env, "") if key_env else ""
        self._base_url = os.environ.get(
            envs.get("base_url", ""),
            envs.get("default_base_url", ""),
        )
        self._model = os.environ.get(
            envs.get("model", ""),
            envs.get("default_model", ""),
        )

        # Validate
        self._validation = self._validate()

    # ── Provider detection ─────────────────────────────────────────────

    def _detect_provider(self) -> str:
        """Detect which provider to use from environment.

        Checks for KEY EXISTENCE (not truthiness) so that an explicitly
        set empty key still triggers the intended provider's validation.
        """
        env_provider = os.environ.get("AGENTCORE_PLANNER_PROVIDER", "").lower()
        if env_provider in _PROVIDER_ENVS:
            return env_provider
        if "OPENAI_API_KEY" in os.environ:
            return "openai"
        if "AGENTCORE_PLANNER_API_KEY" in os.environ:
            base = os.environ.get("AGENTCORE_PLANNER_BASE_URL", "")
            if "openrouter" in base.lower():
                return "openrouter"
            return "openrouter"
        return "mock"

    # ── Validation ────────────────────────────────────────────────────

    def _validate(self) -> tuple[bool, Optional[str]]:
        """Validate configuration. Returns (ready, error)."""
        if self._provider == "mock":
            return True, None

        # API key must be non-empty
        if not self._api_key:
            return False, "API key is empty or not set."

        # Base URL must be valid
        if not self._base_url:
            return False, "Base URL is empty."

        if not _URL_PATTERN.match(self._base_url):
            return False, f"Base URL is not a valid HTTP(S) URL: {self._base_url!r}"

        # Model must be non-empty
        if not self._model:
            return False, "Model name is empty."

        return True, None

    # ── Public API ────────────────────────────────────────────────────

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def api_key(self) -> str:
        """Returns API key. Caller must NOT print/log/persist this."""
        return self._api_key

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def model(self) -> str:
        return self._model

    @property
    def ready(self) -> bool:
        """True if configuration is valid and provider is ready."""
        return self._validation[0]

    @property
    def error(self) -> Optional[str]:
        """Error description if not ready. None when ready."""
        return self._validation[1]

    def as_provider_config(self) -> ProviderConfig:
        """Return a validated ProviderConfig dataclass."""
        return ProviderConfig(
            provider=self._provider,
            api_key=self._api_key,
            base_url=self._base_url,
            model=self._model,
            ready=self.ready,
            error=self.error,
        )

    def __repr__(self) -> str:
        return (
            f"ConfigManager(provider={self._provider!r}, "
            f"base_url={self._base_url!r}, model={self._model!r}, "
            f"ready={self._validation[0]})"
        )
