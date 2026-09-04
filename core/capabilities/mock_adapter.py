# core/capabilities/mock_adapter.py
"""Mock capability adapter — reference implementation for testing Agent-Core capability contracts."""

from __future__ import annotations

from core.capabilities.adapter import BaseCapabilityAdapter
from core.capabilities.schema import CapabilitySpec, CapabilityConstraint, CapabilityResult


class MockEchoCapabilityAdapter(BaseCapabilityAdapter):
    """Mock capability adapter that echoes inputs for runtime verification."""

    def __init__(self, capability_id: str = "mock.echo", fail_mode: bool = False):
        self.capability_id = capability_id
        self.fail_mode = fail_mode

    def get_spec(self) -> CapabilitySpec:
        return CapabilitySpec(
            capability_id=self.capability_id,
            name="Mock Echo Capability",
            description="Mock capability for isolated testing",
            inputs_schema={"text": "str"},
            outputs_schema={"echo": "str"},
            constraints=CapabilityConstraint(read_only=True),
        )

    def execute(self, inputs: dict) -> CapabilityResult:
        if self.fail_mode:
            return CapabilityResult(
                capability_id=self.capability_id,
                status="FAILED",
                error="Simulated capability failure",
            )
        text = str(inputs.get("text", ""))
        return CapabilityResult(
            capability_id=self.capability_id,
            status="SUCCESS",
            output={"echo": f"ECHO: {text}"},
        )
