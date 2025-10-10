#!/usr/bin/env python3
"""End-to-end test for VNC Computer Use Agent.

Usage:
    # Requires GOOGLE_API_KEY and running VNC server
    GOOGLE_API_KEY=your_key python test_e2e.py

    # Or use docker-compose VNC
    docker-compose up -d
    GOOGLE_API_KEY=your_key python test_e2e.py
"""

import argparse
import logging
import os
import sys

from src.vnc_use import VncUseAgent


def setup_logging():
    """Setup logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def test_simple_task():
    """Test with a simple task that should complete quickly."""
    print("\n" + "=" * 60)
    print("End-to-End Test: Simple Desktop Task")
    print("=" * 60)

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("✗ GOOGLE_API_KEY not set")
        return False

    print("\n1. Initializing agent...")
    agent = VncUseAgent(
        vnc_server="localhost::5901",
        vnc_password="vncpassword",
        step_limit=10,  # Keep it short for testing
        seconds_timeout=120,
        hitl_mode=False,  # Disable HITL for automated testing
    )
    print("✓ Agent initialized")

    print("\n2. Running task...")
    task = "Move the mouse to the center of the screen and click once."

    try:
        result = agent.run(task)

        print("\n3. Results:")
        print(f"   Success: {result.get('success')}")
        print(f"   Run ID: {result.get('run_id')}")
        print(f"   Run Dir: {result.get('run_dir')}")

        if result.get("error"):
            print(f"   Error: {result.get('error')}")

        if result.get("success"):
            print("\n✓ Test passed!")
            return True
        print("\n✗ Test failed")
        return False

    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_browser_task():
    """Test with a browser task (more complex)."""
    print("\n" + "=" * 60)
    print("End-to-End Test: Browser Task")
    print("=" * 60)

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("✗ GOOGLE_API_KEY not set")
        return False

    print("\n1. Initializing agent...")
    agent = VncUseAgent(
        vnc_server="localhost::5901",
        vnc_password="vncpassword",
        step_limit=20,
        seconds_timeout=180,
        hitl_mode=False,
        include_initial_screenshot=True,
    )
    print("✓ Agent initialized")

    print("\n2. Running task...")
    task = "Look at the desktop. If you see a browser icon or window, click it to open the browser. Otherwise, just describe what you see on the desktop."

    try:
        result = agent.run(task)

        print("\n3. Results:")
        print(f"   Success: {result.get('success')}")
        print(f"   Run ID: {result.get('run_id')}")
        print(f"   Run Dir: {result.get('run_dir')}")

        if result.get("error"):
            print(f"   Error: {result.get('error')}")

        if result.get("success"):
            print("\n✓ Test passed!")
            return True
        print("\n✗ Test failed")
        return False

    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="End-to-end test for VNC Computer Use")
    parser.add_argument(
        "--test",
        choices=["simple", "browser", "all"],
        default="simple",
        help="Which test to run",
    )

    args = parser.parse_args()

    setup_logging()

    # Check prerequisites
    if not os.getenv("GOOGLE_API_KEY"):
        print("Error: GOOGLE_API_KEY environment variable not set")
        print("Please set it before running: export GOOGLE_API_KEY=your_key")
        sys.exit(1)

    print("Prerequisites:")
    print("✓ GOOGLE_API_KEY set")
    print("✓ Make sure VNC server is running (docker-compose up -d)")

    # Run tests
    if args.test == "simple":
        success = test_simple_task()
        sys.exit(0 if success else 1)

    elif args.test == "browser":
        success = test_browser_task()
        sys.exit(0 if success else 1)

    elif args.test == "all":
        success1 = test_simple_task()
        success2 = test_browser_task()

        print("\n" + "=" * 60)
        print("Summary:")
        print(f"  Simple task: {'✓ PASS' if success1 else '✗ FAIL'}")
        print(f"  Browser task: {'✓ PASS' if success2 else '✗ FAIL'}")
        print("=" * 60)

        sys.exit(0 if (success1 and success2) else 1)


if __name__ == "__main__":
    main()
