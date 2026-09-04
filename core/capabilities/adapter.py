# core/capabilities/adapter.py
"""Capability Adapter & Registry — abstract interface for external replaceable capabilities."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Optional

from core.capabilities.schema import CapabilitySpec, CapabilityResult


class BaseCapabilityAdapter(ABC):
    """Abstract base contract for external capability adapters."""

    @abstractmethod
    def get_spec(self) -> CapabilitySpec:
        """Return the capability specification."""
        pass

    @abstractmethod
    def execute(self, inputs: dict) -> CapabilityResult:
        """Execute the capability action with validated inputs."""
        pass


class CapabilityRegistry:
    """Core registry for managing and invoking capability adapters."""

    def __init__(self):
        self._capabilities: dict[str, BaseCapabilityAdapter] = {}

    def register(self, adapter: BaseCapabilityAdapter) -> None:
        spec = adapter.get_spec()
        self._capabilities[spec.capability_id] = adapter

    def unregister(self, capability_id: str) -> bool:
        if capability_id in self._capabilities:
            del self._capabilities[capability_id]
            return True
        return False

    def get(self, capability_id: str) -> Optional[BaseCapabilityAdapter]:
        return self._capabilities.get(capability_id)

    def list_specs(self) -> list[CapabilitySpec]:
        return [adapter.get_spec() for adapter in self._capabilities.values()]

    def invoke(self, capability_id: str, inputs: dict) -> CapabilityResult:
        adapter = self.get(capability_id)
        if not adapter:
            return CapabilityResult(
                capability_id=capability_id,
                status="FAILED",
                error=f"Capability '{capability_id}' not found in registry",
            )
        t0 = time.time()
        try:
            res = adapter.execute(inputs)
            res.execution_time_seconds = time.time() - t0
            return res
        except Exception as exc:
            return CapabilityResult(
                capability_id=capability_id,
                status="FAILED",
                error=f"Capability execution exception: {exc}",
                execution_time_seconds=time.time() - t0,
            )
