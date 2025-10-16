"""Gemini Computer Use wrapper for VNC desktop control."""

import base64
import logging
import os
from typing import Any

from google import genai
from google.genai.types import (
    ComputerUse,
    Content,
    FunctionResponse,
    GenerateContentConfig,
    Part,
    ThinkingConfig,
    Tool,
)

from .base import BasePlanner


logger = logging.getLogger(__name__)

# Model ID for Gemini Computer Use
MODEL_ID = "gemini-2.5-computer-use-preview-10-2025"


def compress_screenshot(png_bytes: bytes, max_width: int = 512) -> bytes:
    """Compress screenshot to reduce token count.

    Args:
        png_bytes: Original PNG bytes
        max_width: Maximum width in pixels

    Returns:
        Compressed PNG bytes
    """
    import io

    from PIL import Image

    img = Image.open(io.BytesIO(png_bytes))

    # Resize if too large
    if img.width > max_width:
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        logger.debug(f"Resized screenshot to {new_size}")

    # Compress
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True, compress_level=9)
    compressed = buf.getvalue()

    logger.debug(f"Compressed screenshot: {len(png_bytes)} -> {len(compressed)} bytes")
    return compressed


class GeminiPlanner(BasePlanner):
    """Gemini 2.5 Computer Use planner for VNC desktop control.

    Handles request building, response parsing, and function call extraction
    for the Computer Use API with VNC desktop control.
    """

    def __init__(
        self,
        excluded_actions: list[str] | None = None,
        include_thoughts: bool = False,
        api_key: str | None = None,
    ) -> None:
        """Initialize Gemini Computer Use client.

        Args:
            excluded_actions: List of predefined functions to exclude
            include_thoughts: Whether to include model's thinking process
            api_key: Google API key (defaults to GOOGLE_API_KEY env var)
        """
        self.excluded_actions = excluded_actions or []
        self.include_thoughts = include_thoughts

        # Initialize Gemini client
        api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY environment variable not set")

        self.client = genai.Client(api_key=api_key)
        logger.info(f"Initialized Gemini client with model: {MODEL_ID}")

    def build_config(self) -> GenerateContentConfig:
        """Build GenerateContentConfig with Computer Use tool.

        Returns:
            Configuration for Gemini API request
        """
        computer_use = ComputerUse(
            environment="ENVIRONMENT_BROWSER",
            excluded_predefined_functions=self.excluded_actions,
        )

        thinking_config = ThinkingConfig(include_thoughts=self.include_thoughts)

        return GenerateContentConfig(
            tools=[Tool(computer_use=computer_use)],
            thinking_config=thinking_config,
        )

    def start_contents(
        self,
        task: str,
        initial_screenshot_png: bytes | None = None,
    ) -> list[Content]:
        """Build initial user message with task and optional screenshot.

        Args:
            task: User's task description
            initial_screenshot_png: Optional initial screenshot as PNG bytes

        Returns:
            List of Content objects for first request
        """
        parts: list[Part] = []

        # Add task text
        parts.append(Part(text=task))

        # Add initial screenshot if provided
        if initial_screenshot_png:
            # Compress and base64 encode the PNG
            compressed = compress_screenshot(initial_screenshot_png)
            png_b64 = base64.b64encode(compressed).decode("utf-8")
            parts.append(
                Part(
                    inline_data={
                        "mime_type": "image/png",
                        "data": png_b64,
                    }
                )
            )
            logger.debug(f"Added initial screenshot ({len(initial_screenshot_png)} bytes)")

        return [Content(role="user", parts=parts)]

    def generate(
        self,
        contents: list[Content],
        config: GenerateContentConfig | None = None,
    ) -> Any:
        """Call Gemini API with contents.

        Args:
            contents: Conversation history (messages + function responses)
            config: Optional config override (defaults to self.build_config())

        Returns:
            Raw response from Gemini API
        """
        if config is None:
            config = self.build_config()

        # Strip old screenshots from history to avoid token limits
        # Keep only the most recent screenshot in the last function response
        cleaned_contents = []
        for i, content in enumerate(contents):
            if i == len(contents) - 1:
                # Keep last item as-is (most recent screenshot)
                cleaned_contents.append(content)
            else:
                # For older items, remove screenshot data from function responses
                if hasattr(content, "parts") and content.parts:
                    cleaned_parts = []
                    for part in content.parts:
                        if hasattr(part, "function_response") and part.function_response:
                            # Keep function response but remove screenshot
                            fr = part.function_response
                            cleaned_response = {
                                "url": fr.response.get("url", ""),
                            }
                            if "error" in fr.response:
                                cleaned_response["error"] = fr.response["error"]

                            from google.genai.types import FunctionResponse, Part

                            cleaned_parts.append(
                                Part(
                                    function_response=FunctionResponse(
                                        name=fr.name, response=cleaned_response
                                    )
                                )
                            )
                        else:
                            # Keep other parts as-is (text, function_call, etc)
                            cleaned_parts.append(part)

                    from google.genai.types import Content

                    cleaned_contents.append(Content(role=content.role, parts=cleaned_parts))
                else:
                    cleaned_contents.append(content)

        logger.info(
            f"Calling Gemini with {len(cleaned_contents)} content items (old screenshots removed)"
        )

        response = self.client.models.generate_content(
            model=MODEL_ID,
            contents=cleaned_contents,
            config=config,
        )

        return response

    def extract_text(self, response: Any) -> str:
        """Extract text observations/reasoning from Gemini response.

        Args:
            response: Raw Gemini API response

        Returns:
            Text content from model (empty string if none)
        """
        if not hasattr(response, "candidates") or not response.candidates:
            return ""

        candidate = response.candidates[0]
        if not hasattr(candidate, "content") or not candidate.content:
            return ""

        content = candidate.content
        if not hasattr(content, "parts") or not content.parts:
            return ""

        # Extract text from parts
        text_parts = []
        for part in content.parts:
            if hasattr(part, "text") and part.text:
                text_parts.append(part.text)

        return " ".join(text_parts).strip()

    def extract_function_calls(self, response: Any) -> list[dict[str, Any]]:
        """Extract function calls from Gemini response.

        Args:
            response: Raw Gemini API response

        Returns:
            List of dicts with 'name' and 'args' keys
        """
        function_calls: list[dict[str, Any]] = []

        # Navigate response structure
        if not hasattr(response, "candidates") or not response.candidates:
            logger.warning("No candidates in response")
            return function_calls

        candidate = response.candidates[0]
        if not hasattr(candidate, "content") or not candidate.content:
            logger.warning("No content in candidate")
            return function_calls

        content = candidate.content
        if not hasattr(content, "parts") or not content.parts:
            logger.warning("No parts in content")
            return function_calls

        # Extract function calls from parts
        for part in content.parts:
            if hasattr(part, "function_call") and part.function_call:
                fc = part.function_call
                call_dict = {
                    "name": fc.name,
                    "args": dict(fc.args) if fc.args else {},
                }
                function_calls.append(call_dict)
                logger.debug(f"Extracted function call: {fc.name}")

        return function_calls

    def extract_safety_decision(self, response: Any) -> dict[str, Any] | None:
        """Extract safety_decision from Gemini response if present.

        Args:
            response: Raw Gemini API response

        Returns:
            Safety decision dict or None
        """
        # Check if response has safety_decision
        if hasattr(response, "candidates") and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, "safety_decision") and candidate.safety_decision:
                decision = candidate.safety_decision
                return {
                    "action": getattr(decision, "action", None),
                    "reason": getattr(decision, "reason", None),
                }

        return None

    def build_function_response(
        self,
        function_name: str,
        screenshot_png: bytes,
        url: str = "",
        error: str | None = None,
    ) -> Part:
        """Build a FunctionResponse part with screenshot.

        Args:
            function_name: Name of the executed function
            screenshot_png: Screenshot captured after action
            url: Current URL (empty string for VNC desktop)
            error: Optional error message if action failed

        Returns:
            Part containing FunctionResponse
        """
        # Compress and base64 encode the screenshot
        compressed = compress_screenshot(screenshot_png)
        png_b64 = base64.b64encode(compressed).decode("utf-8")

        # Build response data
        response_data = {
            "url": url,
            "screenshot": {
                "mime_type": "image/png",
                "data": png_b64,
            },
        }

        if error:
            response_data["error"] = error

        function_response = FunctionResponse(
            name=function_name,
            response=response_data,
        )

        logger.debug(
            f"Built FunctionResponse for {function_name} ({len(screenshot_png)} bytes screenshot)"
        )

        return Part(function_response=function_response)

    def append_function_response(
        self,
        contents: list[Content],
        function_name: str,
        screenshot_png: bytes,
        url: str = "",
        error: str | None = None,
    ) -> list[Content]:
        """Append a function response to contents.

        Args:
            contents: Existing conversation history
            function_name: Name of executed function
            screenshot_png: Screenshot after action
            url: Current URL (empty for VNC)
            error: Optional error message

        Returns:
            Updated contents list
        """
        response_part = self.build_function_response(
            function_name=function_name,
            screenshot_png=screenshot_png,
            url=url,
            error=error,
        )

        # Function responses go in a user message
        contents.append(Content(role="user", parts=[response_part]))

        return contents

    def generate_stateless(
        self,
        task: str,
        action_history: list[str],
        screenshot_png: bytes,
    ) -> Any:
        """Call Gemini with current screenshot and text context only.

        This is a stateless call that doesn't maintain conversation history.
        Instead, we provide text context about previous actions and the current
        screenshot. This avoids token explosion from accumulated screenshots.

        Args:
            task: Original user task
            action_history: Text log of previous actions and observations
            screenshot_png: Current screenshot

        Returns:
            Raw response from Gemini API
        """
        # Build context message
        context_parts = [f"Task: {task}"]

        if action_history:
            context_parts.append("\nPrevious actions:")
            context_parts.extend(
                f"- {action}" for action in action_history[-10:]
            )  # Last 10 actions

        context_parts.append("\nCurrent screen:")
        context_text = "\n".join(context_parts)

        # Compress and encode screenshot
        compressed = compress_screenshot(screenshot_png)
        png_b64 = base64.b64encode(compressed).decode("utf-8")

        # Build single-turn request
        parts = [
            Part(text=context_text),
            Part(
                inline_data={
                    "mime_type": "image/png",
                    "data": png_b64,
                }
            ),
        ]

        contents = [Content(role="user", parts=parts)]
        config = self.build_config()

        logger.info(f"Stateless call with {len(action_history)} actions in history")

        response = self.client.models.generate_content(
            model=MODEL_ID,
            contents=contents,
            config=config,
        )

        return response


# Backward compatibility alias
GeminiComputerUse = GeminiPlanner
