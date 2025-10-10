#!/usr/bin/env python3
"""Test script for Gemini Computer Use wrapper.

Usage:
    # Test without API key (mock tests only)
    python test_gemini_wrapper.py

    # Test with real API (requires GOOGLE_API_KEY)
    GOOGLE_API_KEY=your_key python test_gemini_wrapper.py --with-api
"""

import argparse
import io
import os
import sys
from unittest.mock import MagicMock

from PIL import Image

from src.vnc_use.backends.vnc import denorm_x, denorm_y
from src.vnc_use.planners.gemini import GeminiComputerUse


def create_mock_screenshot(width: int = 1440, height: int = 900) -> bytes:
    """Create a simple mock PNG screenshot.

    Args:
        width: Image width
        height: Image height

    Returns:
        PNG bytes
    """
    img = Image.new("RGB", (width, height), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_config_building():
    """Test GenerateContentConfig construction."""
    print("\n=== Testing Config Building ===")

    planner = GeminiComputerUse(
        excluded_actions=["open_web_browser"],
        include_thoughts=False,
        api_key="fake_key_for_testing",
    )

    config = planner.build_config()

    assert config is not None, "Config should not be None"
    assert len(config.tools) == 1, "Should have one tool"
    assert config.tools[0].computer_use is not None, "Should have computer_use tool"
    assert "open_web_browser" in config.tools[0].computer_use.excluded_predefined_functions, (
        "Should exclude specified actions"
    )
    assert config.thinking_config.include_thoughts == False, "Should not include thoughts"

    print("  ✓ Config built successfully")
    print("  ✓ Computer Use tool configured")
    print(f"  ✓ Excluded actions: {planner.excluded_actions}")
    print(f"  ✓ Include thoughts: {planner.include_thoughts}")


def test_start_contents():
    """Test initial contents building with task and screenshot."""
    print("\n=== Testing Start Contents ===")

    planner = GeminiComputerUse(api_key="fake_key_for_testing")

    # Test with task only
    contents = planner.start_contents("Open a browser")
    assert len(contents) == 1, "Should have one content item"
    assert contents[0].role == "user", "Should be user role"
    assert len(contents[0].parts) == 1, "Should have one part (text)"
    print("  ✓ Task-only contents built")

    # Test with task + screenshot
    screenshot = create_mock_screenshot()
    contents_with_img = planner.start_contents("Click the button", screenshot)
    assert len(contents_with_img) == 1, "Should have one content item"
    assert len(contents_with_img[0].parts) == 2, "Should have two parts (text + image)"
    print(f"  ✓ Contents with screenshot built ({len(screenshot)} bytes)")


def test_function_response_building():
    """Test FunctionResponse construction."""
    print("\n=== Testing FunctionResponse Building ===")

    planner = GeminiComputerUse(api_key="fake_key_for_testing")
    screenshot = create_mock_screenshot()

    # Test successful action
    part = planner.build_function_response(
        function_name="click_at",
        screenshot_png=screenshot,
        url="",
        error=None,
    )

    assert part.function_response is not None, "Should have function_response"
    assert part.function_response.name == "click_at", "Name should match"
    assert "url" in part.function_response.response, "Should have url field"
    assert "screenshot" in part.function_response.response, "Should have screenshot"
    print("  ✓ FunctionResponse built successfully")
    print(f"  ✓ Function name: {part.function_response.name}")

    # Test failed action with error
    error_part = planner.build_function_response(
        function_name="type_text_at",
        screenshot_png=screenshot,
        url="",
        error="Connection lost",
    )

    assert "error" in error_part.function_response.response, "Should have error field"
    print("  ✓ FunctionResponse with error built")


def test_append_function_response():
    """Test appending function response to contents."""
    print("\n=== Testing Append FunctionResponse ===")

    planner = GeminiComputerUse(api_key="fake_key_for_testing")
    screenshot = create_mock_screenshot()

    # Start with initial contents
    contents = planner.start_contents("Do something")
    initial_len = len(contents)

    # Append a function response
    updated = planner.append_function_response(
        contents=contents,
        function_name="click_at",
        screenshot_png=screenshot,
        url="",
    )

    assert len(updated) == initial_len + 1, "Should have one more content item"
    assert updated[-1].role == "user", "Function response should be user role"
    print(f"  ✓ Function response appended (contents: {initial_len} -> {len(updated)})")


def test_coordinate_denormalization():
    """Test coordinate conversion (from VNC backend)."""
    print("\n=== Testing Coordinate Denormalization ===")

    test_cases = [
        (
            1440,
            900,
            [
                (0, 0, 0, 0),
                (999, 999, 1439, 899),
                (500, 500, 720, 450),
                (250, 750, 360, 675),
            ],
        ),
        (
            1920,
            1080,
            [
                (0, 0, 0, 0),
                (999, 999, 1918, 1079),  # round(999 * 1920 / 1000) = 1918
                (500, 500, 960, 540),
            ],
        ),
    ]

    for width, height, cases in test_cases:
        print(f"\n  Screen size: {width}x{height}")
        for norm_x, norm_y, expected_x, expected_y in cases:
            px = denorm_x(norm_x, width)
            py = denorm_y(norm_y, height)
            assert px == expected_x, f"denorm_x({norm_x}, {width}) should be {expected_x}, got {px}"
            assert py == expected_y, (
                f"denorm_y({norm_y}, {height}) should be {expected_y}, got {py}"
            )
            print(f"    ({norm_x:3}, {norm_y:3}) -> ({px:4}, {py:4}) ✓")

    print("\n  ✓ All coordinate conversions correct")


def test_extract_function_calls():
    """Test extraction of function calls from mock response."""
    print("\n=== Testing Function Call Extraction ===")

    planner = GeminiComputerUse(api_key="fake_key_for_testing")

    # Create a mock response with function calls
    mock_fc = MagicMock()
    mock_fc.name = "click_at"
    mock_fc.args = {"x": 500, "y": 300}

    mock_part = MagicMock()
    mock_part.function_call = mock_fc

    mock_content = MagicMock()
    mock_content.parts = [mock_part]

    mock_candidate = MagicMock()
    mock_candidate.content = mock_content

    mock_response = MagicMock()
    mock_response.candidates = [mock_candidate]

    # Extract function calls
    calls = planner.extract_function_calls(mock_response)

    assert len(calls) == 1, "Should extract one function call"
    assert calls[0]["name"] == "click_at", "Function name should match"
    assert calls[0]["args"]["x"] == 500, "Args should match"
    assert calls[0]["args"]["y"] == 300, "Args should match"

    print("  ✓ Function calls extracted successfully")
    print(f"  ✓ Extracted: {calls[0]['name']}({calls[0]['args']})")


def test_with_real_api():
    """Test with real Gemini API (requires GOOGLE_API_KEY)."""
    print("\n=== Testing with Real Gemini API ===")

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("  ⚠ GOOGLE_API_KEY not set, skipping real API test")
        return False

    try:
        planner = GeminiComputerUse()
        print("  ✓ Client initialized")

        # Create a mock screenshot
        screenshot = create_mock_screenshot()

        # Build initial contents with a simple task
        contents = planner.start_contents(
            "Look at this desktop screenshot and describe what you see.",
            initial_screenshot_png=screenshot,
        )

        print("  ✓ Initial contents built with screenshot")

        # Call API
        print("  ⏳ Calling Gemini API...")
        response = planner.generate(contents)

        print("  ✓ API call successful")

        # Extract function calls
        function_calls = planner.extract_function_calls(response)
        print(f"  ✓ Extracted {len(function_calls)} function call(s)")

        if function_calls:
            for fc in function_calls:
                print(f"    - {fc['name']}({fc['args']})")

        # Extract safety decision
        safety = planner.extract_safety_decision(response)
        if safety:
            print(f"  ✓ Safety decision: {safety}")
        else:
            print("  ✓ No safety decision required")

        # Test appending a function response
        if function_calls:
            fc = function_calls[0]
            new_screenshot = create_mock_screenshot()
            contents = planner.append_function_response(
                contents=contents,
                function_name=fc["name"],
                screenshot_png=new_screenshot,
            )
            print("  ✓ Appended function response")

        return True

    except Exception as e:
        print(f"  ✗ API test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="Test Gemini wrapper")
    parser.add_argument(
        "--with-api",
        action="store_true",
        help="Run tests with real Gemini API (requires GOOGLE_API_KEY)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Testing Gemini Computer Use Wrapper")
    print("=" * 60)

    # Run mock tests (no API required)
    try:
        test_config_building()
        test_start_contents()
        test_function_response_building()
        test_append_function_response()
        test_coordinate_denormalization()
        test_extract_function_calls()

        print("\n" + "=" * 60)
        print("✓ All mock tests passed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Mock tests failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # Run real API test if requested
    if args.with_api:
        success = test_with_real_api()
        if success:
            print("\n" + "=" * 60)
            print("✓ Real API test passed!")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("✗ Real API test failed")
            print("=" * 60)
            sys.exit(1)
    else:
        print("\n(Skipping real API tests. Use --with-api to test with Gemini API)")

    sys.exit(0)


if __name__ == "__main__":
    main()
