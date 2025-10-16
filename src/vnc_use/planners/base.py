"""Abstract base planner interface for multi-model support."""

from abc import ABC, abstractmethod
from typing import Any


class BasePlanner(ABC):
    """Abstract base class for LLM planners.

    Provides a common interface for different LLM providers (Gemini, Anthropic, etc.)
    to propose actions based on screenshots and task descriptions.
    """

    @abstractmethod
    def generate_stateless(
        self,
        task: str,
        action_history: list[str],
        screenshot_png: bytes,
    ) -> Any:
        """Generate model response with action proposals.

        Args:
            task: User's task description
            action_history: List of text descriptions of past actions
            screenshot_png: Current screenshot as PNG bytes

        Returns:
            Raw model response (format varies by provider)
        """
        ...

    @abstractmethod
    def extract_text(self, response: Any) -> str:
        """Extract text observations/reasoning from model response.

        Args:
            response: Raw model response

        Returns:
            Text content from model (empty string if none)
        """
        ...

    @abstractmethod
    def extract_function_calls(self, response: Any) -> list[dict[str, Any]]:
        """Extract function calls from model response.

        Args:
            response: Raw model response

        Returns:
            List of dicts with 'name' and 'args' keys:
            [{"name": "click_at", "args": {"x": 100, "y": 200}}, ...]
        """
        ...

    @abstractmethod
    def extract_safety_decision(self, response: Any) -> dict[str, Any] | None:
        """Extract safety decision from model response if present.

        Args:
            response: Raw model response

        Returns:
            Safety decision dict with 'action' and 'reason' keys, or None
            Example: {"action": "require_confirmation", "reason": "Risky operation"}
        """
        ...
