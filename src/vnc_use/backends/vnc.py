"""VNC backend controller for executing UI actions."""

import io
import logging
import tempfile
from pathlib import Path
from typing import Literal

from PIL import Image
from vncdotool import api as vnc_api

from ..types import ActionResult


logger = logging.getLogger(__name__)


def denorm_x(x: int, width: int) -> int:
    """Convert normalized x coordinate (0-999) to pixel x.

    Args:
        x: Normalized x coordinate (0-999)
        width: Screen width in pixels

    Returns:
        Pixel x coordinate
    """
    return round(x * width / 1000)


def denorm_y(y: int, height: int) -> int:
    """Convert normalized y coordinate (0-999) to pixel y.

    Args:
        y: Normalized y coordinate (0-999)
        height: Screen height in pixels

    Returns:
        Pixel y coordinate
    """
    return round(y * height / 1000)


class VNCController:
    """Controller for VNC desktop interactions.

    Handles screenshot capture, mouse operations, keyboard input, and scrolling
    via vncdotool. Automatically converts normalized coordinates (0-999) to
    pixels based on current screen size.
    """

    def __init__(self) -> None:
        """Initialize VNC controller (not yet connected)."""
        self.client: vnc_api.VNCDoToolClient | None = None
        self._screen_size: tuple[int, int] | None = None

    def connect(self, server: str, password: str | None = None) -> "VNCController":
        """Connect to VNC server.

        Args:
            server: VNC server address (e.g., "localhost::5901" or "host:port")
            password: Optional VNC password

        Returns:
            Self for method chaining

        Raises:
            Exception: If connection fails
        """
        logger.info(f"Connecting to VNC server: {server}")
        self.client = vnc_api.connect(server, password=password)
        logger.info("VNC connection established")
        return self

    def disconnect(self) -> None:
        """Disconnect from VNC server."""
        if self.client:
            self.client.disconnect()
            self.client = None
            logger.info("VNC connection closed")

    def screenshot_png(self) -> bytes:
        """Capture current screen as PNG bytes.

        Returns:
            PNG screenshot as bytes

        Raises:
            RuntimeError: If not connected
        """
        if not self.client:
            raise RuntimeError("Not connected to VNC server")

        # Capture to temporary file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            self.client.captureScreen(str(tmp_path))
            png_bytes = tmp_path.read_bytes()

            # Update cached screen size
            img = Image.open(io.BytesIO(png_bytes))
            self._screen_size = img.size
            logger.debug(f"Screenshot captured: {img.size}")

            return png_bytes
        finally:
            tmp_path.unlink(missing_ok=True)

    def get_screen_size(self) -> tuple[int, int]:
        """Get current screen dimensions.

        Returns:
            Tuple of (width, height) in pixels

        Raises:
            RuntimeError: If screen size not yet known (capture screenshot first)
        """
        if not self._screen_size:
            raise RuntimeError("Screen size unknown; capture screenshot first")
        return self._screen_size

    def move(self, x: int, y: int) -> None:
        """Move mouse pointer to pixel coordinates.

        Args:
            x: Pixel x coordinate
            y: Pixel y coordinate

        Raises:
            RuntimeError: If not connected
        """
        if not self.client:
            raise RuntimeError("Not connected to VNC server")
        self.client.mouseMove(x, y)
        logger.debug(f"Mouse moved to ({x}, {y})")

    def click(self, x: int, y: int, button: int = 1) -> None:
        """Click at pixel coordinates.

        Args:
            x: Pixel x coordinate
            y: Pixel y coordinate
            button: Mouse button (1=left, 2=middle, 3=right)

        Raises:
            RuntimeError: If not connected
        """
        if not self.client:
            raise RuntimeError("Not connected to VNC server")

        # Move first to avoid injection glitches
        self.client.mouseMove(x, y)
        self.client.mousePress(button)
        logger.debug(f"Clicked button {button} at ({x}, {y})")

    def double_click(self, x: int, y: int) -> None:
        """Double-click at pixel coordinates.

        Args:
            x: Pixel x coordinate
            y: Pixel y coordinate

        Raises:
            RuntimeError: If not connected
        """
        if not self.client:
            raise RuntimeError("Not connected to VNC server")

        self.client.mouseMove(x, y)
        self.client.mousePress(1)
        self.client.mousePress(1)
        logger.debug(f"Double-clicked at ({x}, {y})")

    def drag_and_drop(self, x0: int, y0: int, x1: int, y1: int) -> None:
        """Drag from one point to another.

        Args:
            x0: Start pixel x
            y0: Start pixel y
            x1: End pixel x
            y1: End pixel y

        Raises:
            RuntimeError: If not connected
        """
        if not self.client:
            raise RuntimeError("Not connected to VNC server")

        self.client.mouseMove(x0, y0)
        self.client.mouseDown(1)
        self.client.mouseDrag(x1, y1)
        self.client.mouseUp(1)
        logger.debug(f"Dragged from ({x0}, {y0}) to ({x1}, {y1})")

    def type_text(self, text: str, press_enter: bool = False, clear_first: bool = False) -> None:
        """Type text at current cursor position.

        Args:
            text: Text to type
            press_enter: Whether to press Enter after typing
            clear_first: Whether to clear existing text first (Ctrl+A, Delete)

        Raises:
            RuntimeError: If not connected
        """
        if not self.client:
            raise RuntimeError("Not connected to VNC server")

        if clear_first:
            self.client.keyPress("ctrl-a")
            self.client.keyPress("delete")

        # vncdotool handles string typing
        for char in text:
            self.client.keyPress(char)

        if press_enter:
            self.client.keyPress("enter")

        logger.debug(f"Typed text: {text[:50]}{'...' if len(text) > 50 else ''}")

    def key_combo(self, keys: str) -> None:
        """Execute keyboard shortcut.

        Args:
            keys: Key combination (e.g., "control+a", "alt+tab")

        Raises:
            RuntimeError: If not connected
        """
        if not self.client:
            raise RuntimeError("Not connected to VNC server")

        # vncdotool accepts "ctrl-a" format; normalize input
        normalized = keys.replace("+", "-").replace("control", "ctrl")
        self.client.keyPress(normalized)
        logger.debug(f"Pressed key combo: {keys}")

    def scroll(
        self,
        direction: Literal["up", "down", "left", "right"],
        magnitude: int = 800,
    ) -> None:
        """Scroll in a direction.

        Uses PageUp/PageDown/Arrow keys with magnitude-based repetition.

        Args:
            direction: Scroll direction
            magnitude: Scroll distance (divided by 400 for repetitions)

        Raises:
            RuntimeError: If not connected
        """
        if not self.client:
            raise RuntimeError("Not connected to VNC server")

        # Map direction to key
        key_map = {
            "up": "pgup",
            "down": "pgdn",
            "left": "left",
            "right": "right",
        }
        key = key_map[direction]

        # Repeat based on magnitude (heuristic: 400 pixels per press)
        repeats = max(1, magnitude // 400)
        for _ in range(repeats):
            self.client.keyPress(key)

        logger.debug(f"Scrolled {direction} with magnitude {magnitude} ({repeats} repeats)")

    def execute_action(
        self,
        action_name: str,
        args: dict,
    ) -> ActionResult:
        """Execute a Computer Use action and capture result.

        Args:
            action_name: Name of action to execute
            args: Action arguments (with normalized coordinates if applicable)

        Returns:
            ActionResult with screenshot and execution status
        """
        try:
            width, height = self.get_screen_size()

            if action_name == "click_at":
                px = denorm_x(args["x"], width)
                py = denorm_y(args["y"], height)
                self.click(px, py)

            elif action_name == "hover_at":
                px = denorm_x(args["x"], width)
                py = denorm_y(args["y"], height)
                self.move(px, py)

            elif action_name == "type_text_at":
                px = denorm_x(args["x"], width)
                py = denorm_y(args["y"], height)
                self.click(px, py)  # Focus first
                self.type_text(
                    args["text"],
                    press_enter=args.get("press_enter", False),
                    clear_first=args.get("clear_before_typing", False),
                )

            elif action_name == "key_combination":
                self.key_combo(args["keys"])

            elif action_name == "scroll_document":
                self.scroll(args["direction"], args.get("magnitude", 800))

            elif action_name == "scroll_at":
                px = denorm_x(args["x"], width)
                py = denorm_y(args["y"], height)
                self.move(px, py)  # Move to location first
                self.scroll(args["direction"], args.get("magnitude", 800))

            elif action_name == "drag_and_drop":
                x0 = denorm_x(args["x"], width)
                y0 = denorm_y(args["y"], height)
                x1 = denorm_x(args["destination_x"], width)
                y1 = denorm_y(args["destination_y"], height)
                self.drag_and_drop(x0, y0, x1, y1)

            elif action_name == "open_web_browser":
                # No-op: rely on user's VM having browser available
                logger.info("open_web_browser: no-op (rely on pinned browser)")

            else:
                raise ValueError(f"Unknown action: {action_name}")

            # Capture screenshot after action
            screenshot = self.screenshot_png()

            return ActionResult(
                success=True,
                error=None,
                screenshot_png=screenshot,
                url="",  # VNC desktop has no URL
            )

        except Exception as e:
            logger.error(f"Action {action_name} failed: {e}")
            # Still try to capture screenshot for debugging
            try:
                screenshot = self.screenshot_png()
            except:
                screenshot = b""

            return ActionResult(
                success=False,
                error=str(e),
                screenshot_png=screenshot,
                url="",
            )
