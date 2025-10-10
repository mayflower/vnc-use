#!/usr/bin/env python3
"""Test script for VNC backend functionality.

Usage:
    python test_vnc_backend.py --vnc localhost::5901 [--password PASSWORD]

Tests:
1. Connection and screenshot capture
2. Coordinate denormalization
3. Mouse click action
4. Keyboard typing action
5. Scroll action
"""

import argparse
import sys
from pathlib import Path

from src.vnc_use.backends.vnc import VNCController, denorm_x, denorm_y


def test_denormalization():
    """Test coordinate conversion from 0-999 to pixels."""
    print("\n=== Testing Coordinate Denormalization ===")

    # Test with 1440x900 screen
    width, height = 1440, 900

    # Test corners and center
    test_cases = [
        (0, 0, "top-left"),
        (999, 0, "top-right"),
        (0, 999, "bottom-left"),
        (999, 999, "bottom-right"),
        (500, 500, "center"),
    ]

    for norm_x, norm_y, desc in test_cases:
        px = denorm_x(norm_x, width)
        py = denorm_y(norm_y, height)
        print(f"  {desc:12} ({norm_x:3}, {norm_y:3}) -> ({px:4}, {py:3})")

    # Verify specific expectations (999 maps to width-1 due to 0-999 range)
    assert denorm_x(0, width) == 0, "Left edge should be 0"
    assert denorm_x(999, width) == 1439, "Right edge should be width-1"
    assert denorm_x(500, width) == 720, "Center x should be ~half width"
    assert denorm_y(0, height) == 0, "Top edge should be 0"
    assert denorm_y(999, height) == 899, "Bottom edge should be height-1"
    assert denorm_y(500, height) == 450, "Center y should be ~half height"

    print("  ✓ All denormalization tests passed")


def test_vnc_connection(vnc_server: str, password: str | None = None):
    """Test VNC connection and basic operations."""
    print(f"\n=== Testing VNC Connection to {vnc_server} ===")

    controller = VNCController()

    try:
        # Test connection
        print("  Connecting...")
        controller.connect(vnc_server, password)
        print("  ✓ Connected successfully")

        # Test screenshot capture
        print("  Capturing screenshot...")
        screenshot = controller.screenshot_png()
        print(f"  ✓ Screenshot captured: {len(screenshot)} bytes")

        # Get screen size
        width, height = controller.get_screen_size()
        print(f"  ✓ Screen size: {width}x{height}")

        # Save screenshot for inspection
        output_path = Path("test_screenshot.png")
        output_path.write_bytes(screenshot)
        print(f"  ✓ Screenshot saved to {output_path}")

        # Test mouse movement to center
        print("\n  Testing mouse movement to center...")
        center_x = denorm_x(500, width)
        center_y = denorm_y(500, height)
        controller.move(center_x, center_y)
        print(f"  ✓ Moved mouse to center ({center_x}, {center_y})")

        # Test click at current position
        print("  Testing click at center...")
        controller.click(center_x, center_y)
        print("  ✓ Click executed")

        # Test keyboard input
        print("  Testing keyboard input...")
        controller.type_text("test", press_enter=False)
        print("  ✓ Typed 'test'")

        # Test key combo
        print("  Testing key combination...")
        controller.key_combo("ctrl+a")
        print("  ✓ Pressed Ctrl+A")

        # Test scroll
        print("  Testing scroll down...")
        controller.scroll("down", magnitude=400)
        print("  ✓ Scrolled down")

        # Capture final screenshot
        print("\n  Capturing final screenshot...")
        final_screenshot = controller.screenshot_png()
        final_path = Path("test_screenshot_final.png")
        final_path.write_bytes(final_screenshot)
        print(f"  ✓ Final screenshot saved to {final_path}")

        # Test execute_action wrapper
        print("\n  Testing execute_action wrapper...")
        result = controller.execute_action(
            "click_at",
            {"x": 500, "y": 500},
        )
        print(f"  ✓ execute_action succeeded: {result.success}")
        if result.error:
            print(f"    Warning: {result.error}")

        print("\n✓ All VNC tests passed!")

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        print("\n  Disconnecting...")
        controller.disconnect()
        print("  ✓ Disconnected")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Test VNC backend",
        epilog="Tip: Start test VNC with 'docker-compose up -d' first",
    )
    parser.add_argument(
        "--vnc",
        default="localhost::5901",
        help="VNC server address (default: localhost::5901 for docker-compose)",
    )
    parser.add_argument(
        "--password",
        default="vncpassword",
        help="VNC password (default: vncpassword for docker-compose)",
    )
    parser.add_argument(
        "--skip-connection",
        action="store_true",
        help="Skip connection tests (only test denormalization)",
    )

    args = parser.parse_args()

    # Always test denormalization (no VNC required)
    test_denormalization()

    # Test VNC connection if not skipped
    if not args.skip_connection:
        success = test_vnc_connection(args.vnc, args.password)
        sys.exit(0 if success else 1)
    else:
        print("\n(Skipping VNC connection tests)")
        sys.exit(0)


if __name__ == "__main__":
    main()
