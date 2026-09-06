# core/runtime/decision.py
"""Decision Engine — deterministic action validation and policy authorization.

Ensures LLM reasoning proposes actions, but deterministic policy & registry validation
selects and authorizes execution.
"""

from __future__ import annotations

from typing import Any, Optional, Union

from core.capabilities.adapter import CapabilityRegistry
from core.kernel.policy import PolicyEngine
from core.runtime.state import AgentAction


class DecisionResult:
    """Outcome of action validation and authorization decision."""

    def __init__(
        self,
        authorized_action: Optional[AgentAction],
        authorization_status: str,  # ALLOW | DENY | ASK_USER
        reason: str,
    ):
        self.authorized_action = authorized_action
        self.authorization_status = authorization_status
        self.reason = reason

    @property
    def is_allowed(self) -> bool:
        return self.authorization_status == "ALLOW" and self.authorized_action is not None

    @property
    def requires_user(self) -> bool:
        return self.authorization_status == "ASK_USER"

    @property
    def is_denied(self) -> bool:
        return self.authorization_status == "DENY"


class DecisionEngine:
    """Deterministic layer validating actions, registry availability, and policy authorization."""

    def __init__(self, registry: CapabilityRegistry, policy: PolicyEngine):
        self._registry = registry
        self._policy = policy

    def evaluate_action(
        self,
        proposed_action: Union[AgentAction, dict[str, Any]],
        user_approved: bool = False,
    ) -> DecisionResult:
        """Validate proposed action and authorize against PolicyEngine.

        Pipeline:
            1. Parse/validate action structure
            2. Verify capability exists in registry
            3. Check policy authorization
            4. Return ALLOW / DENY / ASK_USER decision
        """
        # 1. Parse / Validate structure
        if isinstance(proposed_action, dict):
            try:
                action = AgentAction.from_dict(proposed_action)
            except Exception as exc:
                return DecisionResult(
                    authorized_action=None,
                    authorization_status="DENY",
                    reason=f"Malformed action structure: {exc}",
                )
        elif isinstance(proposed_action, AgentAction):
            action = proposed_action
        else:
            return DecisionResult(
                authorized_action=None,
                authorization_status="DENY",
                reason=f"Invalid action type: {type(proposed_action)}",
            )

        if not action.capability or not action.operation:
            return DecisionResult(
                authorized_action=None,
                authorization_status="DENY",
                reason="Action missing required 'capability' or 'operation' field",
            )

        # 2. Capability Registry validation
        adapter = self._registry.get(action.capability)
        if not adapter:
            return DecisionResult(
                authorized_action=action,
                authorization_status="DENY",
                reason=f"Capability '{action.capability}' not registered in CapabilityRegistry",
            )

        spec = adapter.get_spec()

        # Build full input map including operation
        inputs = dict(action.arguments) if action.arguments else {}
        if "action" not in inputs:
            inputs["action"] = action.operation

        # 3. PolicyEngine Authorization
        authorized, reason = self._policy.authorize_capability(
            capability_spec=spec,
            action=action.operation,
            inputs=inputs,
            user_approved=user_approved,
        )

        if authorized:
            return DecisionResult(
                authorized_action=action,
                authorization_status="ALLOW",
                reason="Action authorized by policy engine",
            )

        # Check if denial was due to missing user approval for a write/mutation action
        if reason and "requires explicit user approval" in reason and not user_approved:
            return DecisionResult(
                authorized_action=action,
                authorization_status="ASK_USER",
                reason=reason,
            )

        return DecisionResult(
            authorized_action=action,
            authorization_status="DENY",
            reason=reason or "Policy prohibited action execution",
        )
