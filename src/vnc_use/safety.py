"""Safety and HITL (Human-in-the-Loop) handling."""

import logging
from typing import Literal


logger = logging.getLogger(__name__)


def requires_confirmation(safety_decision: dict | None) -> bool:
    """Check if safety decision requires user confirmation.

    Args:
        safety_decision: Safety decision from Gemini response

    Returns:
        True if confirmation required
    """
    if not safety_decision:
        return False

    action = safety_decision.get("action", "").lower()
    return "confirm" in action or action == "require_confirmation"


def should_block(safety_decision: dict | None) -> bool:
    """Check if safety decision blocks execution.

    Args:
        safety_decision: Safety decision from Gemini response

    Returns:
        True if execution should be blocked
    """
    if not safety_decision:
        return False

    action = safety_decision.get("action", "").lower()
    return action in ("block", "deny", "reject")


class HITLGate:
    """Human-in-the-Loop gate for safety confirmations.

    Manages approval/denial state for actions requiring confirmation.
    """

    def __init__(self) -> None:
        """Initialize HITL gate."""
        self.pending_decision: Literal["approve", "deny"] | None = None
        self.pending_reason: str | None = None

    def request_confirmation(self, safety_decision: dict, pending_calls: list) -> None:
        """Log confirmation request.

        Args:
            safety_decision: Safety decision requiring confirmation
            pending_calls: Pending function calls
        """
        reason = safety_decision.get("reason", "Unknown reason")
        logger.warning(f"⚠️  HITL confirmation required: {reason}")
        logger.info(f"Pending calls: {[c['name'] for c in pending_calls]}")

    def set_decision(self, decision: Literal["approve", "deny"], reason: str = "") -> None:
        """Set user decision.

        Args:
            decision: User's decision (approve or deny)
            reason: Optional reason for decision
        """
        self.pending_decision = decision
        self.pending_reason = reason
        logger.info(f"HITL decision: {decision} ({reason})")

    def approve(self, reason: str = "User approved") -> None:
        """Approve pending action.

        Args:
            reason: Reason for approval
        """
        self.set_decision("approve", reason)

    def deny(self, reason: str = "User denied") -> None:
        """Deny pending action.

        Args:
            reason: Reason for denial
        """
        self.set_decision("deny", reason)

    def get_decision(self) -> Literal["approve", "deny"] | None:
        """Get current decision.

        Returns:
            Current decision or None if not set
        """
        return self.pending_decision

    def is_approved(self) -> bool:
        """Check if action is approved.

        Returns:
            True if approved
        """
        return self.pending_decision == "approve"

    def is_denied(self) -> bool:
        """Check if action is denied.

        Returns:
            True if denied
        """
        return self.pending_decision == "deny"

    def reset(self) -> None:
        """Reset decision state."""
        self.pending_decision = None
        self.pending_reason = None
