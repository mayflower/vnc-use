# Testing Guide

## Quick Start with Docker

### 1. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and set your GOOGLE_API_KEY
# GOOGLE_API_KEY=your_google_api_key_here
```

### 2. Start All Services

```bash
# Start VNC desktop and MCP server
docker-compose up -d

# Check services are running
docker-compose ps
```

This starts:
- Ubuntu desktop with XFCE and Chromium (accessible via VNC)
- MCP server with streaming HTTP transport at http://localhost:8001/mcp

### 3. Access the Services

**VNC Desktop:**
- Web Browser (noVNC): http://localhost:6901 (password: `vncpassword`)
- VNC Client: `localhost:5901` (password: `vncpassword`)

**MCP Server:**
- HTTP endpoint: http://localhost:8001/mcp
- Logs: `docker-compose logs -f mcp-server`

### 4. Run the Tests

#### VNC Backend Tests

```bash
# Test coordinate denormalization only (no VNC required)
uv run python tests/test_vnc_backend.py --skip-connection

# Test with the Docker VNC desktop (using default settings)
uv run python tests/test_vnc_backend.py

# Or specify VNC server explicitly
uv run python tests/test_vnc_backend.py --vnc localhost::5901 --password vncpassword
```

#### Gemini Wrapper Tests

```bash
# Run without API (mock tests only)
uv run python tests/test_gemini_wrapper.py

# Run with real API
export GOOGLE_API_KEY=your_key
uv run python tests/test_gemini_wrapper.py --with-api
```

#### End-to-End Tests

```bash
export GOOGLE_API_KEY=your_key
docker-compose up -d

# Simple desktop task
uv run python tests/test_e2e.py --test simple

# Browser task - Navigate to Mayflower blog and extract headlines
uv run python tests/test_browser_search.py

# Shell command tests - Use terminal to check system information
uv run python tests/test_shell_commands.py --test df    # Check disk space
uv run python tests/test_shell_commands.py --test free  # Check memory usage
uv run python tests/test_shell_commands.py --test all   # Run both
```

#### Using pytest (Recommended)

```bash
# Install dev dependencies
uv sync --extra dev

# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_vnc_backend.py

# Run with verbose output
uv run pytest -v

# Run specific test function
uv run pytest tests/test_vnc_backend.py::test_coordinate_denormalization
```

### 5. Test the MCP Server

**Check MCP Server Status:**
```bash
# View MCP server logs
docker-compose logs -f mcp-server

# Test MCP server health
curl http://localhost:8001/mcp
```

**Test with MCP Client:**
```python
# test_mcp_client.py
import asyncio
from fastmcp import Client

async def test():
    async with Client("http://localhost:8001/mcp") as client:
        tools = await client.list_tools()
        print(f"Available tools: {[t.name for t in tools]}")

        result = await client.call_tool(
            "execute_vnc_task",
            {
                "vnc_server": "vnc-desktop::5901",
                "vnc_password": "vncpassword",
                "task": "Click on the desktop",
                "step_limit": 5,
            }
        )
        print(f"Result: {result}")

asyncio.run(test())
```

### 6. Test Descriptions

#### Browser Automation Test (`test_browser_search.py`)
This test demonstrates the agent's ability to:
- Open a web browser in the VNC desktop
- Navigate to blog.mayflower.de
- Wait for the page to load completely
- Visually identify and read blog post headlines
- Extract and report the latest 3-5 headlines

This replaces the previous Google search test and shows the agent can navigate to specific websites and extract content.

#### Shell Command Tests (`test_shell_commands.py`)
These tests demonstrate the agent's ability to:
- Open a terminal application in the desktop environment
- Type shell commands (df, free)
- Execute commands by pressing Enter
- Read and interpret command output
- Report system information

Available tests:
- `--test df`: Check disk space usage with `df -h`
- `--test free`: Check memory usage with `free -h`
- `--test all`: Run both disk and memory tests

### 7. Stop the Containers

```bash
docker-compose down
```

## Container Configuration

The Docker container is configured with:
- **Resolution:** 1440x900 (matches default in code)
- **VNC Port:** 5901
- **noVNC Port:** 6901 (web-based access)
- **Password:** `vncpassword`

To change settings, edit `docker-compose.yml` environment variables.

## Troubleshooting

### Connection refused
- Ensure the container is running: `docker-compose ps`
- Check logs: `docker-compose logs -f vnc-desktop`

### Wrong screen size
- The test will auto-detect actual screen size from screenshots
- To change resolution, edit `VNC_RESOLUTION` in docker-compose.yml

### VNC client issues
- Use `::` separator for vncdotool: `localhost::5901`
- Use `:` separator for standard VNC clients: `localhost:5901`
