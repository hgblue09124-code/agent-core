# core/capabilities/schema.py
"""Capability schema — specification, constraints, and execution results for external capabilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CapabilityConstraint:
    """Constraints imposed on capability execution."""

    max_execution_time_seconds: float = 30.0
    requires_user_approval: bool = False
    read_only: bool = True
    allowed_domains: list[str] = field(default_factory=list)


@dataclass
class CapabilitySpec:
    """Formal contract specification for a pluggable capability."""

    capability_id: str
    name: str
    description: str
    version: str = "1.0.0"
    inputs_schema: dict[str, str] = field(default_factory=dict)
    outputs_schema: dict[str, str] = field(default_factory=dict)
    constraints: CapabilityConstraint = field(default_factory=CapabilityConstraint)

    def to_dict(self) -> dict:
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "inputs_schema": self.inputs_schema,
            "outputs_schema": self.outputs_schema,
            "constraints": {
                "max_execution_time_seconds": self.constraints.max_execution_time_seconds,
                "requires_user_approval": self.constraints.requires_user_approval,
                "read_only": self.constraints.read_only,
                "allowed_domains": list(self.constraints.allowed_domains),
            },
        }


@dataclass
class CapabilityResult:
    """Execution output from a capability invocation."""

    capability_id: str
    status: str  # SUCCESS | FAILED | DENIED
    output: Any = None
    error: Optional[str] = None
    execution_time_seconds: float = 0.0
    metadata: dict = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.status == "SUCCESS"
