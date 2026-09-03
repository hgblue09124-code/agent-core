# core/knowledge/lifecycle.py
"""Strict state machine for knowledge lifecycle transitions."""

from core.knowledge.schema import KnowledgeStatus


# Legal transitions: from_state -> set of allowed to_states
_LEGAL_TRANSITIONS: dict[str, set[str]] = {
    KnowledgeStatus.CANDIDATE.value: {
        KnowledgeStatus.VALIDATED.value,
        KnowledgeStatus.REJECTED.value,
    },
    KnowledgeStatus.VALIDATED.value: {
        KnowledgeStatus.VERIFIED.value,
        KnowledgeStatus.DEPRECATED.value,
        KnowledgeStatus.REJECTED.value,
    },
    KnowledgeStatus.VERIFIED.value: {
        KnowledgeStatus.ACTIVE.value,
        KnowledgeStatus.DEPRECATED.value,
    },
    KnowledgeStatus.ACTIVE.value: {
        KnowledgeStatus.DEPRECATED.value,
    },
    KnowledgeStatus.DEPRECATED.value: set(),
    KnowledgeStatus.REJECTED.value: set(),
}


class LifecycleError(ValueError):
    """Raised when an illegal state transition is attempted."""
    pass


class Lifecycle:
    """Enforces legal state transitions.

    Usage:
        lc = Lifecycle()
        lc.can_transition(current, target)   # bool
        lc.apply(current, target)            # raises LifecycleError or returns target
    """

    def can_transition(self, from_state: str, to_state: str) -> bool:
        """Return True if the transition is legal."""
        return to_state in _LEGAL_TRANSITIONS.get(from_state, set())

    def apply(self, from_state: str, to_state: str) -> str:
        """Apply transition or raise LifecycleError.

        Returns the new state string.
        """
        if not self.can_transition(from_state, to_state):
            raise LifecycleError(
                f"Illegal transition: {from_state} → {to_state}. "
                f"Allowed from {from_state}: {_LEGAL_TRANSITIONS.get(from_state, set())}"
            )
        return to_state
