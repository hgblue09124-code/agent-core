# core/capabilities/bridge.py
"""Bridge adapter for external capability frameworks (agent-capabilities).

Architectural Ownership:
- Core provides abstract capability adapter contracts (BaseCapabilityAdapter, CapabilityRegistry).
- External capabilities framework (agent-capabilities) provides concrete capability implementations & dispatchers.
- ExternalCapabilityBridge maps external capability contracts into Core's CapabilityRegistry without duplicating logic.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from core.capabilities.adapter import BaseCapabilityAdapter
from core.capabilities.schema import CapabilityConstraint, CapabilityResult, CapabilitySpec

logger = logging.getLogger(__name__)


class ExternalCapabilityBridge(BaseCapabilityAdapter):
    """Bridge adapter wrapping an external agent-capabilities capability object."""

    def __init__(self, external_capability: Any):
        self._external = external_capability
        self._spec = self._extract_spec()

    def _extract_spec(self) -> CapabilitySpec:
        """Extract or adapt spec from external capability object."""
        if hasattr(self._external, "get_spec"):
            ext_spec = self._external.get_spec()
            if isinstance(ext_spec, CapabilitySpec):
                return ext_spec
            if isinstance(ext_spec, dict):
                constraints_dict = ext_spec.get("constraints", {})
                return CapabilitySpec(
                    capability_id=ext_spec.get("capability_id", "external_capability"),
                    name=ext_spec.get("name", "External Capability"),
                    description=ext_spec.get("description", "Bridged external capability"),
                    version=ext_spec.get("version", "1.0.0"),
                    inputs_schema=ext_spec.get("inputs_schema", {}),
                    outputs_schema=ext_spec.get("outputs_schema", {}),
                    constraints=CapabilityConstraint(
                        max_execution_time_seconds=constraints_dict.get("max_execution_time_seconds", 30.0),
                        requires_user_approval=constraints_dict.get("requires_user_approval", False),
                        read_only=constraints_dict.get("read_only", True),
                        allowed_domains=constraints_dict.get("allowed_domains", []),
                    ),
                )

        # Fallback inspection of external attributes
        cap_id = getattr(self._external, "capability_id", getattr(self._external, "name", "external_capability"))
        name = getattr(self._external, "name", str(cap_id))
        desc = getattr(self._external, "description", "Bridged external capability")

        return CapabilitySpec(
            capability_id=str(cap_id),
            name=str(name),
            description=str(desc),
            version="1.0.0",
            constraints=CapabilityConstraint(read_only=True),
        )

    def get_spec(self) -> CapabilitySpec:
        """Return the converted capability spec."""
        return self._spec

    def execute(self, inputs: dict[str, Any]) -> CapabilityResult:
        """Execute the external capability with boundary exception safety."""
        try:
            if hasattr(self._external, "execute"):
                res = self._external.execute(inputs)
            elif hasattr(self._external, "dispatch"):
                res = self._external.dispatch(self._spec.capability_id, inputs)
            elif callable(self._external):
                res = self._external(inputs)
            else:
                return CapabilityResult(
                    capability_id=self._spec.capability_id,
                    status="FAILED",
                    error=f"External object '{type(self._external).__name__}' has no execute/dispatch method",
                )

            if isinstance(res, CapabilityResult):
                return res

            if isinstance(res, dict):
                return CapabilityResult(
                    capability_id=self._spec.capability_id,
                    status=res.get("status", "SUCCESS" if res.get("success", True) else "FAILED"),
                    output=res.get("output", res.get("data")),
                    error=res.get("error"),
                    metadata=res.get("metadata", {}),
                )

            return CapabilityResult(
                capability_id=self._spec.capability_id,
                status="SUCCESS",
                output=res,
            )
        except Exception as exc:
            logger.error(f"External capability bridge execution error for '{self._spec.capability_id}': {exc}")
            # External capability failure must NOT compromise Core integrity
            return CapabilityResult(
                capability_id=self._spec.capability_id,
                status="FAILED",
                error=f"Bridged execution exception: {exc}",
            )
