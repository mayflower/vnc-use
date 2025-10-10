"""VNC Computer Use Agent - Gemini-powered desktop automation via VNC."""

from .agent import VncUseAgent
from .backends.vnc import VNCController
from .planners.gemini import GeminiComputerUse
from .types import ActionResult, CUAState


__version__ = "0.1.0"

__all__ = [
    "ActionResult",
    "CUAState",
    "GeminiComputerUse",
    "VNCController",
    "VncUseAgent",
]
