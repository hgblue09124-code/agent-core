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


class SuccessCapability(BaseCapabilityAdapter):
    """Deterministic capability that always succeeds with valid evidence."""

    def __init__(self, capability_id: str = "mock.success"):
        self.capability_id = capability_id

    def get_spec(self) -> CapabilitySpec:
        return CapabilitySpec(
            capability_id=self.capability_id,
            name="Success Capability",
            description="Deterministic success capability",
            inputs_schema={},
            outputs_schema={"result": "str"},
            constraints=CapabilityConstraint(read_only=True),
        )

    def execute(self, inputs: dict) -> CapabilityResult:
        return CapabilityResult(
            capability_id=self.capability_id,
            status="SUCCESS",
            output={"result": "OK", "action": inputs.get("action", "execute")},
            metadata={"evidence": "valid_evidence_payload"},
        )


class FailOnceCapability(BaseCapabilityAdapter):
    """Deterministic capability that fails on first call, then succeeds on retry."""

    def __init__(self, capability_id: str = "mock.fail_once"):
        self.capability_id = capability_id
        self.call_count = 0

    def get_spec(self) -> CapabilitySpec:
        return CapabilitySpec(
            capability_id=self.capability_id,
            name="Fail Once Capability",
            description="Fails on first call then succeeds",
            inputs_schema={},
            outputs_schema={"result": "str"},
            constraints=CapabilityConstraint(read_only=True),
        )

    def execute(self, inputs: dict) -> CapabilityResult:
        self.call_count += 1
        if self.call_count == 1:
            return CapabilityResult(
                capability_id=self.capability_id,
                status="FAILED",
                error="Transient execution failure (attempt 1)",
            )
        return CapabilityResult(
            capability_id=self.capability_id,
            status="SUCCESS",
            output={"result": f"OK on attempt {self.call_count}"},
            metadata={"evidence": "retry_success_evidence"},
        )


class AlwaysFailCapability(BaseCapabilityAdapter):
    """Deterministic capability that always fails."""

    def __init__(self, capability_id: str = "mock.always_fail"):
        self.capability_id = capability_id

    def get_spec(self) -> CapabilitySpec:
        return CapabilitySpec(
            capability_id=self.capability_id,
            name="Always Fail Capability",
            description="Always fails execution",
            inputs_schema={},
            outputs_schema={},
            constraints=CapabilityConstraint(read_only=True),
        )

    def execute(self, inputs: dict) -> CapabilityResult:
        return CapabilityResult(
            capability_id=self.capability_id,
            status="FAILED",
            error="Persistent execution failure",
        )


class MutationCapability(BaseCapabilityAdapter):
    """Mutation capability requiring explicit user approval (write action)."""

    def __init__(self, capability_id: str = "mock.mutation"):
        self.capability_id = capability_id

    def get_spec(self) -> CapabilitySpec:
        return CapabilitySpec(
            capability_id=self.capability_id,
            name="Mutation Capability",
            description="Modifies state and requires approval",
            inputs_schema={"action": "str"},
            outputs_schema={"status": "str"},
            constraints=CapabilityConstraint(read_only=False, requires_user_approval=True),
        )

    def execute(self, inputs: dict) -> CapabilityResult:
        act = inputs.get("action", "create_record")
        return CapabilityResult(
            capability_id=self.capability_id,
            status="SUCCESS",
            output={"status": f"Mutated state via {act}"},
            metadata={"mutation_approved": True},
        )


class EvidenceMissingCapability(BaseCapabilityAdapter):
    """Capability that returns status=SUCCESS but lacks valid output/evidence."""

    def __init__(self, capability_id: str = "mock.evidence_missing"):
        self.capability_id = capability_id

    def get_spec(self) -> CapabilitySpec:
        return CapabilitySpec(
            capability_id=self.capability_id,
            name="Evidence Missing Capability",
            description="Returns status SUCCESS but evidence is missing",
            inputs_schema={},
            outputs_schema={},
            constraints=CapabilityConstraint(read_only=True),
        )

    def execute(self, inputs: dict) -> CapabilityResult:
        return CapabilityResult(
            capability_id=self.capability_id,
            status="SUCCESS",
            output={"data": "evidence_missing_data", "details": "evidence_missing"},
            metadata={},
        )
