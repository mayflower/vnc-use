"""Type definitions for vnc-use agent."""

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field


class StepLog(TypedDict):
    """Log entry for a single execution step."""

    step_number: int
    observation: str  # Model's text observation/reasoning
    proposed_actions: list[dict[str, Any]]  # All actions proposed by model
    executed_action: dict[str, Any]  # The action that was executed
    result: str  # Success/Error message
    screenshot_path: str | None  # Path to screenshot after this step
    timestamp: float  # When this step occurred


class CUAState(TypedDict):
    """LangGraph state for Computer Use Agent.

    Tracks text-only action history (no screenshots), pending function calls
    to execute, and execution status. Screenshots are sent to Gemini on each
    turn but not stored in history to avoid token limits.
    """

    task: str
    action_history: list[str]  # Text-only log of actions and observations
    step_logs: list[StepLog]  # Structured logs for report generation
    pending_calls: list[dict[str, Any]]  # buffered function calls from last response
    last_screenshot_png: bytes | None
    step: int
    done: bool
    safety: dict[str, Any] | None  # last safety_decision (if any)
    start_time: float  # wall-clock start for timeout
    error: str | None  # terminal error message


class ActionResult(BaseModel):
    """Result of executing a single action on VNC."""

    success: bool
    error: str | None = None
    screenshot_png: bytes
    url: str = ""  # empty for VNC desktop; populated if browser URL available


class VNCAction(BaseModel):
    """Parsed action from Gemini function call."""

    name: str
    args: dict[str, Any]


class ClickAction(BaseModel):
    """Click at normalized coordinates."""

    x: int = Field(ge=0, le=999)
    y: int = Field(ge=0, le=999)


class HoverAction(BaseModel):
    """Hover at normalized coordinates."""

    x: int = Field(ge=0, le=999)
    y: int = Field(ge=0, le=999)


class TypeTextAction(BaseModel):
    """Type text at normalized coordinates."""

    x: int = Field(ge=0, le=999)
    y: int = Field(ge=0, le=999)
    text: str
    press_enter: bool = False
    clear_before_typing: bool = False


class KeyCombinationAction(BaseModel):
    """Execute keyboard shortcut."""

    keys: str  # e.g., "control+a", "alt+tab"


class ScrollDocumentAction(BaseModel):
    """Scroll the whole document."""

    direction: Literal["up", "down", "left", "right"]
    magnitude: int = 800


class ScrollAtAction(BaseModel):
    """Scroll at specific normalized coordinates."""

    x: int = Field(ge=0, le=999)
    y: int = Field(ge=0, le=999)
    direction: Literal["up", "down", "left", "right"]
    magnitude: int = 800


class DragAndDropAction(BaseModel):
    """Drag from one point to another."""

    x: int = Field(ge=0, le=999)
    y: int = Field(ge=0, le=999)
    destination_x: int = Field(ge=0, le=999)
    destination_y: int = Field(ge=0, le=999)
