#!/usr/bin/env python3
"""Test browser-based Google search.

Usage:
    docker-compose up -d
    GEMINI_API_KEY=your_key python test_browser_search.py
"""

import logging
import os
import sys

from src.vnc_use import VncUseAgent


def test_google_search():
    """Test opening browser, searching Google, and extracting first result URL."""
    print("\n" + "=" * 70)
    print("Testing: Browser Search for 'computer use anthropic'")
    print("=" * 70)

    # Check prerequisites
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("✗ Error: GEMINI_API_KEY or GOOGLE_API_KEY not set")
        return False

    print("\n✓ API key found")
    print("✓ Make sure docker-compose is running (docker-compose up -d)")

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    print("\n1. Initializing agent...")
    agent = VncUseAgent(
        vnc_server="localhost::5901",
        vnc_password="vncpassword",
        step_limit=20,  # Allow more steps for this complex task
        seconds_timeout=300,  # 5 minutes
        hitl_mode=False,  # No human intervention
    )
    print("   ✓ Agent initialized")

    print("\n2. Running search task...")
    print("   Task: Open browser, search for 'computer use anthropic', get first URL")

    # Create detailed task instructions
    task = """Open a web browser (if not already open).
Navigate to Google.com.
Search for "computer use anthropic".
After the search results appear, identify and report the URL of the first search result.
The URL should be the actual destination URL, not the Google redirect link."""

    try:
        result = agent.run(task)

        print("\n3. Results:")
        print(f"   Success: {result.get('success')}")
        print(f"   Steps completed: {result.get('final_state', {}).get('step', 0)}")
        print(f"   Run directory: {result.get('run_dir')}")

        if result.get("error"):
            print(f"   Error: {result.get('error')}")

        # Check if we got far enough
        final_state = result.get("final_state", {})
        steps = final_state.get("step", 0)

        if result.get("success") and steps >= 3:
            print("\n✓ Test completed!")
            print(f"  The agent executed {steps} steps.")
            print(f"  Check the run artifacts for screenshots: {result.get('run_dir')}")
            print("\nNote: Due to the nature of Computer Use, the agent may have")
            print("encountered token limits. Check the screenshots in the run directory")
            print("to see how far it got and what actions it performed.")
            return True
        print("\n⚠ Test incomplete")
        print(f"  Only {steps} steps completed (expected at least 3)")
        if result.get("error"):
            print(f"  Error: {result.get('error')}")
        return False

    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    print("=" * 70)
    print("Google Search Test for VNC Computer Use Agent")
    print("=" * 70)
    print("\nThis test will:")
    print("  1. Open a browser in the VNC desktop")
    print("  2. Navigate to Google")
    print("  3. Search for 'computer use anthropic'")
    print("  4. Attempt to extract the first result URL")
    print("\nNote: Due to Gemini API token limits (131K), the agent may")
    print("complete only a few steps before hitting limits. This is a known")
    print("limitation when using high-resolution screenshots.")
    print("=" * 70)

    success = test_google_search()

    print("\n" + "=" * 70)
    if success:
        print("Test completed - check run artifacts for results")
    else:
        print("Test incomplete - see error messages above")
    print("=" * 70)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
