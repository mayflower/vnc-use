"""Anthropic Claude planner for VNC desktop control using LangChain."""

import base64
import logging
import os
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from .base import BasePlanner
from .gemini import compress_screenshot
from .vnc_tools import get_vnc_tools


logger = logging.getLogger(__name__)

# Default model for Anthropic
DEFAULT_MODEL = "claude-haiku-4-5-20251015"


class AnthropicPlanner(BasePlanner):
    """Anthropic Claude planner for VNC desktop control.

    Uses LangChain's ChatAnthropic with tool calling to propose VNC actions
    based on screenshots and task descriptions.
    """

    def __init__(
        self,
        excluded_actions: list[str] | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        """Initialize Anthropic Claude planner.

        Args:
            excluded_actions: List of action names to exclude
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            model: Model name (defaults to claude-haiku-4-5-20251015)
        """
        self.excluded_actions = excluded_actions or []
        self.model = model or os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL)

        # Initialize Anthropic client via LangChain
        api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        self.llm = ChatAnthropic(
            model=self.model,
            api_key=api_key,
            temperature=0.0,
        )

        # Get VNC tool schemas (excluding specified actions)
        tool_schemas = get_vnc_tools(excluded_actions)

        # Bind tools to LLM
        self.llm_with_tools = self.llm.bind_tools(list(tool_schemas.values()))

        logger.info(f"Initialized Anthropic planner with model: {self.model}")
        logger.info(f"Available tools: {list(tool_schemas.keys())}")

    def generate_stateless(
        self,
        task: str,
        action_history: list[str],
        screenshot_png: bytes,
    ) -> AIMessage:
        """Generate model response with action proposals.

        Args:
            task: User's task description
            action_history: List of text descriptions of past actions
            screenshot_png: Current screenshot as PNG bytes

        Returns:
            LangChain AIMessage with tool calls
        """
        # Compress screenshot
        compressed = compress_screenshot(screenshot_png, max_width=512)
        screenshot_b64 = base64.b64encode(compressed).decode("utf-8")

        # Build messages
        messages = []

        # System message with task context
        system_prompt = f"""You are controlling a computer via VNC (Virtual Network Computing).
You can see screenshots of the desktop and propose actions to accomplish tasks.

Current task: {task}

Available actions:
- click_at: Click at coordinates (x, y normalized to 0-999)
- double_click_at: Double-click at coordinates
- type_text_at: Click at coordinates then type text
- key_combination: Press keyboard shortcuts (e.g., 'control+c')
- scroll_document: Scroll the current document
- scroll_at: Scroll at specific coordinates
- drag_and_drop: Drag from one location to another
- hover_at: Move mouse to hover at coordinates

Coordinates are normalized to a 0-999 grid. Convert screen positions proportionally.
"""

        if action_history:
            system_prompt += "\n\nActions taken so far:\n" + "\n".join(
                f"{i + 1}. {action}" for i, action in enumerate(action_history)
            )

        messages.append(SystemMessage(content=system_prompt))

        # User message with screenshot
        user_content = [
            {
                "type": "text",
                "text": "Here is the current screenshot. What action(s) should I take next to accomplish the task?",
            },
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"},
            },
        ]

        messages.append(HumanMessage(content=user_content))

        logger.debug(
            f"Calling Anthropic with screenshot ({len(screenshot_png)} -> {len(compressed)} bytes)"
        )

        # Invoke model with tools
        response: AIMessage = self.llm_with_tools.invoke(messages)

        logger.info(f"Received response with {len(response.tool_calls)} tool call(s)")

        return response

    def extract_text(self, response: AIMessage) -> str:
        """Extract text observations/reasoning from model response.

        Args:
            response: LangChain AIMessage

        Returns:
            Text content from model (empty string if none)
        """
        if isinstance(response.content, str):
            return response.content
        if isinstance(response.content, list):
            # Extract text from content blocks
            text_parts = []
            for block in response.content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    text_parts.append(block)
            return " ".join(text_parts).strip()
        return ""

    def extract_function_calls(self, response: AIMessage) -> list[dict[str, Any]]:
        """Extract function calls from model response.

        Args:
            response: LangChain AIMessage

        Returns:
            List of dicts with 'name' and 'args' keys
        """
        function_calls = []

        for tool_call in response.tool_calls:
            # LangChain tool_call format: {"name": str, "args": dict, "id": str}
            function_calls.append({"name": tool_call["name"], "args": tool_call["args"]})
            logger.debug(f"Extracted function call: {tool_call['name']}")

        return function_calls

    def extract_safety_decision(self, response: AIMessage) -> dict[str, Any] | None:
        """Extract safety decision from model response if present.

        Anthropic Claude doesn't have the same safety_decision structure as Gemini.
        We detect refusals or safety concerns by analyzing the response content.

        Args:
            response: LangChain AIMessage

        Returns:
            Safety decision dict or None
        """
        # Check if response has no tool calls and contains refusal language
        if not response.tool_calls:
            text = self.extract_text(response)
            refusal_indicators = [
                "i cannot",
                "i can't",
                "i'm not able to",
                "unsafe",
                "dangerous",
                "i shouldn't",
                "i won't",
                "cannot comply",
            ]

            text_lower = text.lower()
            for indicator in refusal_indicators:
                if indicator in text_lower:
                    logger.warning(f"Detected potential refusal: {text[:100]}")
                    return {"action": "block", "reason": f"Model refused: {text[:200]}"}

        # No safety concerns detected
        return None
