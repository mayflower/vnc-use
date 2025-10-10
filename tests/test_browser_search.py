#!/usr/bin/env python3
"""Test browser-based navigation to Mayflower blog and headline extraction.

Usage:
    docker-compose up -d
    GEMINI_API_KEY=your_key python tests/test_browser_search.py
"""

import logging
import os
import sys

from src.vnc_use import VncUseAgent


def test_mayflower_blog_headlines():
    """Test opening browser, visiting blog.mayflower.de, and extracting headlines."""
    print("\n" + "=" * 70)
    print("Testing: Visit blog.mayflower.de and Get Latest Headlines")
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
        step_limit=25,  # Allow enough steps for browser navigation
        seconds_timeout=300,  # 5 minutes
        hitl_mode=False,  # No human intervention
    )
    print("   ✓ Agent initialized")

    print("\n2. Running blog headline extraction task...")
    print("   Task: Navigate to blog.mayflower.de and extract recent headlines")

    # Create detailed task instructions
    task = """Open a web browser (if not already open).
Navigate to blog.mayflower.de.
Wait for the page to load completely.
Look at the blog posts on the page and identify the headlines or titles of the most recent blog posts.
Report the first 3-5 blog post headlines you can see."""

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

        if result.get("success") and steps >= 5:
            print("\n✓ Test completed!")
            print(f"  The agent executed {steps} steps.")
            print(f"  Check the run artifacts for screenshots: {result.get('run_dir')}")
            print("  Look at the EXECUTION_REPORT.md for the extracted headlines")
            print("\nNote: The agent should have navigated to blog.mayflower.de")
            print("and attempted to read the blog post headlines from the page.")
            return True
        print("\n⚠ Test incomplete")
        print(f"  Only {steps} steps completed (expected at least 5)")
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
    print("Mayflower Blog Headlines Test for VNC Computer Use Agent")
    print("=" * 70)
    print("\nThis test will:")
    print("  1. Open a browser in the VNC desktop")
    print("  2. Navigate to blog.mayflower.de")
    print("  3. Wait for page to load")
    print("  4. Extract and report the latest blog post headlines")
    print("\nNote: The agent will use Computer Use to visually identify")
    print("and read headlines from the blog page.")
    print("=" * 70)

    success = test_mayflower_blog_headlines()

    print("\n" + "=" * 70)
    if success:
        print("Test completed - check run artifacts for results")
    else:
        print("Test incomplete - see error messages above")
    print("=" * 70)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
