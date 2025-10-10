#!/usr/bin/env python3
"""Test shell command execution via Computer Use.

This test verifies that the agent can open a terminal and execute
shell commands to retrieve system information.

Usage:
    docker-compose up -d
    GEMINI_API_KEY=your_key python tests/test_shell_commands.py
"""

import logging
import os
import sys

from src.vnc_use import VncUseAgent


def test_df_memory_check():
    """Test opening terminal, running 'df -h' to check disk space."""
    print("\n" + "=" * 70)
    print("Testing: Shell Command - Check Free Memory with 'df -h'")
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
        step_limit=30,  # Allow enough steps to open terminal and run command
        seconds_timeout=300,  # 5 minutes
        hitl_mode=False,  # No human intervention
    )
    print("   ✓ Agent initialized")

    print("\n2. Running shell command task...")
    print("   Task: Open terminal and check disk space using 'df -h'")

    # Create detailed task instructions
    task = """Open a terminal application on the desktop.
Once the terminal is open, type the command 'df -h' and press Enter to execute it.
Wait for the command output to appear.
Read and report the disk space information shown by the df command.
Focus on the filesystem mounted at '/' (root) and report its size, used space, available space, and usage percentage."""

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
            print("  Look at the EXECUTION_REPORT.md for the df command output")
            print("\nNote: The agent should have:")
            print("  - Opened a terminal application")
            print("  - Typed and executed 'df -h'")
            print("  - Read the disk space information from the output")
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


def test_free_memory_check():
    """Test running 'free -h' to check memory usage."""
    print("\n" + "=" * 70)
    print("Testing: Shell Command - Check Memory Usage with 'free -h'")
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
        step_limit=30,  # Allow enough steps to open terminal and run command
        seconds_timeout=300,  # 5 minutes
        hitl_mode=False,  # No human intervention
    )
    print("   ✓ Agent initialized")

    print("\n2. Running shell command task...")
    print("   Task: Open terminal and check memory usage with 'free -h'")

    # Create detailed task instructions
    task = """Open a terminal application on the desktop.
Once the terminal is open, type the command 'free -h' and press Enter to execute it.
Wait for the command output to appear.
Read and report the memory usage information, including total memory, used memory, free memory, and available memory."""

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
            print("  Look at the EXECUTION_REPORT.md for the free command output")
            print("\nNote: The agent should have:")
            print("  - Opened a terminal application")
            print("  - Typed and executed 'free -h'")
            print("  - Read the memory usage information from the output")
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
    import argparse

    parser = argparse.ArgumentParser(description="Shell command integration tests")
    parser.add_argument(
        "--test",
        choices=["df", "free", "all"],
        default="df",
        help="Which test to run (default: df)",
    )

    args = parser.parse_args()

    print("=" * 70)
    print("Shell Command Integration Tests for VNC Computer Use Agent")
    print("=" * 70)

    if args.test == "df":
        print("\nThis test will:")
        print("  1. Open a terminal in the VNC desktop")
        print("  2. Type and execute 'df -h' command")
        print("  3. Read and report disk space information")
        print("\nNote: The agent uses Computer Use to visually interact")
        print("with the terminal and read command output.")
        print("=" * 70)

        success = test_df_memory_check()

        print("\n" + "=" * 70)
        if success:
            print("Test completed - check run artifacts for results")
        else:
            print("Test incomplete - see error messages above")
        print("=" * 70)

        sys.exit(0 if success else 1)

    elif args.test == "free":
        print("\nThis test will:")
        print("  1. Open a terminal in the VNC desktop")
        print("  2. Type and execute 'free -h' command")
        print("  3. Read and report memory usage information")
        print("\nNote: The agent uses Computer Use to visually interact")
        print("with the terminal and read command output.")
        print("=" * 70)

        success = test_free_memory_check()

        print("\n" + "=" * 70)
        if success:
            print("Test completed - check run artifacts for results")
        else:
            print("Test incomplete - see error messages above")
        print("=" * 70)

        sys.exit(0 if success else 1)

    elif args.test == "all":
        print("\nThis will run both shell command tests:")
        print("  1. df -h (disk space)")
        print("  2. free -h (memory usage)")
        print("=" * 70)

        success1 = test_df_memory_check()
        success2 = test_free_memory_check()

        print("\n" + "=" * 70)
        print("Summary:")
        print(f"  df -h test: {'✓ PASS' if success1 else '✗ FAIL'}")
        print(f"  free -h test: {'✓ PASS' if success2 else '✗ FAIL'}")
        print("=" * 70)

        sys.exit(0 if (success1 and success2) else 1)


if __name__ == "__main__":
    main()
