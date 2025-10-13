#!/usr/bin/env python3
"""Test MCP server via HTTP to get latest news from heise.de.

This test demonstrates the full MCP stack:
- MCP server running in Docker
- HTTP streaming transport
- VNC desktop control
- Browser automation to extract news headlines

Usage:
    # Start Docker services first
    docker-compose up -d

    # Wait for services to be ready
    sleep 5

    # Run the test
    python tests/test_mcp_http_heise.py
"""

import asyncio
import sys

from fastmcp import Client


async def test_heise_news_via_mcp():
    """Test getting heise.de news via MCP HTTP server."""
    print("\n" + "=" * 70)
    print("Testing: MCP HTTP Server - Get Latest News from heise.de")
    print("=" * 70)

    print("\n1. Connecting to MCP server...")
    print("   URL: http://localhost:8001/mcp")

    try:
        async with Client("http://localhost:8001/mcp") as client:
            print("   ✓ Connected to MCP server")

            # List available tools
            print("\n2. Discovering available tools...")
            tools = await client.list_tools()
            tool_names = [t.name for t in tools]
            print(f"   Available tools: {tool_names}")

            if "execute_vnc_task" not in tool_names:
                print("   ✗ Error: execute_vnc_task tool not found")
                return False

            print("   ✓ Found execute_vnc_task tool")

            # Execute task to get heise.de news
            print("\n3. Executing VNC task...")
            print("   Task: Navigate to heise.de and extract latest news headlines")
            print("   Hostname: vnc-desktop (credentials from server-side store)")
            print("   This may take 1-2 minutes...")

            task = """Open a web browser (if not already open).
Navigate to heise.de (the German tech news site).
Wait for the page to load completely.
Look at the news section and identify the headlines of the most recent news articles.
Report the first 5 news headlines you can see on the page."""

            result = await client.call_tool(
                "execute_vnc_task",
                {
                    "hostname": "vnc-desktop",  # Credentials looked up from server-side store
                    "task": task,
                    "step_limit": 30,  # Allow enough steps for browser + navigation
                    "timeout": 300,  # 5 minutes
                },
            )

            # FastMCP returns CallToolResult, extract content
            result_data = result.content[0].text if result.content else "{}"
            import json

            result_dict = json.loads(result_data) if isinstance(result_data, str) else result_data

            print("\n4. Results:")
            print(f"   Success: {result_dict.get('success')}")
            print(f"   Steps executed: {result_dict.get('steps', 0)}")
            print(f"   Run ID: {result_dict.get('run_id')}")
            print(f"   Run directory: {result_dict.get('run_dir')}")

            if result_dict.get("error"):
                print(f"   Error: {result_dict.get('error')}")

            # Check if task completed successfully
            if result_dict.get("success") and result_dict.get("steps", 0) >= 5:
                print("\n✓ Test completed successfully!")
                print(f"  The agent executed {result_dict.get('steps')} steps.")
                print(f"  Run artifacts saved to: {result_dict.get('run_dir')}")
                print("\nTo view the results:")
                print(f"  1. Check screenshots: ls {result_dict.get('run_dir')}/*.png")
                print(
                    f"  2. Read execution report: cat {result_dict.get('run_dir')}/EXECUTION_REPORT.md"
                )
                print("  3. View in browser: http://localhost:6901 (VNC desktop)")
                print("\nNote: The extracted headlines should be visible in the")
                print("model's observations in the EXECUTION_REPORT.md file.")
                return True
            print("\n⚠ Test incomplete or failed")
            print(f"  Steps completed: {result_dict.get('steps', 0)}")
            if result_dict.get("error"):
                print(f"  Error: {result_dict.get('error')}")
            return False

    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback

        traceback.print_exc()
        return False


def check_prerequisites():
    """Check if Docker services are running."""
    print("\nChecking prerequisites...")

    import subprocess

    try:
        # Check VNC desktop container
        result = subprocess.run(
            ["docker-compose", "ps", "-q", "vnc-desktop"],
            capture_output=True,
            text=True,
        )
        if result.stdout.strip():
            print("✓ VNC desktop container is running")
        else:
            print("✗ VNC desktop container not running")
            print("\nPlease start Docker services:")
            print("  docker-compose up -d")
            return False

        # Check MCP server container
        result = subprocess.run(
            ["docker-compose", "ps", "-q", "mcp-server"],
            capture_output=True,
            text=True,
        )
        if result.stdout.strip():
            print("✓ MCP server container is running")
        else:
            print("✗ MCP server container not running")
            print("\nPlease start Docker services:")
            print("  docker-compose up -d")
            return False

        print("✓ All Docker services are running")
        print("  Note: MCP server uses streaming protocol, simple HTTP checks won't work")
        return True

    except Exception as e:
        print(f"✗ Error checking prerequisites: {e}")
        return False


def main():
    print("=" * 70)
    print("MCP HTTP Test: Get Latest News from heise.de")
    print("=" * 70)
    print("\nThis test demonstrates:")
    print("  1. Connecting to MCP server via HTTP (port 8001)")
    print("  2. Calling execute_vnc_task tool with streaming")
    print("  3. Opening browser in VNC desktop")
    print("  4. Navigating to heise.de")
    print("  5. Extracting and reporting news headlines")
    print("\nRequirements:")
    print("  - Docker services running (docker-compose up -d)")
    print("  - MCP server accessible at http://localhost:8001/mcp")
    print("  - VNC desktop running on vnc-desktop::5901")
    print("=" * 70)

    if not check_prerequisites():
        print("\n✗ Prerequisites not met. Exiting.")
        sys.exit(1)

    print("\nStarting test...")
    success = asyncio.run(test_heise_news_via_mcp())

    print("\n" + "=" * 70)
    if success:
        print("TEST PASSED - Check run artifacts for extracted headlines")
    else:
        print("TEST FAILED - See error messages above")
    print("=" * 70)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
