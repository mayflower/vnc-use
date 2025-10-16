# vnc-use

**LangGraph agent for Computer Use via VNC with Multi-Model LLM Support**

A Python package that enables autonomous desktop interaction through VNC using state-of-the-art Computer Use models (Gemini 2.5 or Anthropic Claude Haiku 4.5). The agent runs a tight *observe → propose → act* loop, grounding actions directly from screenshots without OCR or template matching.

## Features

- **Multi-model LLM support** - Choose between Gemini 2.5 Computer Use or Anthropic Claude Haiku 4.5
- **Direct screenshot grounding** - No OCR, no template matching (per Computer Use design)
- **Generic desktop automation** - Works with any VNC-accessible desktop
- **Secure credential management** - Multi-tenant support with OS keyring, .netrc, or environment variables
- **Safety-first HITL** - Optional human-in-the-loop gates for risky actions
- **Coordinate denormalization** - Handles any screen resolution
- **LangGraph orchestration** - Stateless vision architecture for efficient token usage
- **Structured logging** - Full run artifacts with screenshots at each step
- **Markdown execution reports** - Human-readable reports with embedded screenshots showing what the agent saw, thought, and did
- **MCP server** - FastMCP 2.0 streaming server for AI agent integration

## Architecture

The agent implements a continuous observe-propose-act loop:

```
Task
  ↓
Observe (VNC Screenshot)
  ↓
Propose (LLM: Gemini or Claude)
  ↓
HITL Gate (if confirmation needed)
  ↓
Act (Execute on VNC)
  ↓
Loop until done or timeout
```

## Model Selection

vnc-use supports multiple LLM providers through a pluggable architecture:

| Provider | Model | Best For | Speed | Cost |
|----------|-------|----------|-------|------|
| **Gemini** | `gemini-2.5-computer-use-preview-10-2025` | Complex tasks, multi-step workflows | Medium | Medium |
| **Anthropic** | `claude-haiku-4-5-20251015` | Fast responses, cost optimization | Fast | Low |

**Select via environment variable:**
```bash
# Use Anthropic Claude Haiku 4.5 (faster, cheaper)
export MODEL_PROVIDER=anthropic
export ANTHROPIC_API_KEY=sk-ant-...

# Use Gemini 2.5 Computer Use (default)
export MODEL_PROVIDER=gemini
export GOOGLE_API_KEY=...
```

**Or via CLI flag:**
```bash
vnc-use run --model-provider anthropic --task "..."
vnc-use run --model-provider gemini --task "..."
```

Both models use the same VNC backend, HITL safety, and action execution infrastructure.

**Key Design Decisions:**
- **Stateless vision**: Each turn sends only the current screenshot + text history (no screenshot accumulation)
- **Normalized coordinates**: Gemini returns 0-999 coords, automatically converted to pixels
- **Safety gates**: Optional human-in-the-loop for risky actions
- **Structured logging**: Every run generates detailed artifacts including markdown reports

## Installation

```bash
# Clone repository
git clone git@github.com:mayflower/vnc-use.git
cd vnc-use

# Install with uv
uv sync

# Or with pip
pip install -e .

# Optional: Install OS keyring support for encrypted credential storage
pip install -e ".[keyring]"
```

**Dependencies:**
- Python 3.10+
- LangGraph, Google GenAI SDK, vncdotool, Pillow, FastMCP
- Optional: `keyring` package for OS-encrypted credential storage

## Quick Start

### 1. Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your Google API key
# GOOGLE_API_KEY=your_google_api_key_here
```

### 2. Start Services with Docker

```bash
# Start both VNC desktop and MCP server
docker-compose up -d

# Check services are running
docker-compose ps
```

**Available services:**
- VNC Desktop (web): http://localhost:6901 (password: vncpassword)
- VNC Desktop (VNC): localhost:5901
- MCP Server: http://localhost:8001/mcp

### 3. Run a Task with Docker

**Using the MCP Server:**
```bash
# The MCP server is now running at http://localhost:8001/mcp
# Use any MCP client to connect and call the execute_vnc_task tool
```

**Using Python API (local):**
```bash
# If running locally without Docker, set API key
export GOOGLE_API_KEY=your_google_api_key
```

### 4. Run Tasks

**CLI:**
```bash
uv run vnc-use run --task "Open a browser and search for LangGraph"
```

**Python API:**
```python
from vnc_use import VncUseAgent

# First, configure credentials (one-time setup):
# vnc-use-credentials set localhost --server localhost::5901 --password vncpassword

# Then use the agent (credentials looked up automatically):
agent = VncUseAgent(
    vnc_server="localhost::5901",
    vnc_password="vncpassword",  # Or omit if using credential store
    step_limit=40,
    seconds_timeout=300,
    hitl_mode=True,  # Enable safety confirmations
)

result = agent.run("Open the browser and navigate to google.com")
print(f"Success: {result['success']}")
print(f"Artifacts: {result['run_dir']}")
```

**MCP Server:**
```python
# Docker MCP server is pre-configured with vnc-desktop credentials
# For custom servers, configure credentials first:
# vnc-use-credentials set my-vnc --server my-vnc.example.com::5901

import asyncio
from fastmcp import Client

async def run_task():
    async with Client("http://localhost:8001/mcp") as client:
        result = await client.call_tool(
            "execute_vnc_task",
            {
                "hostname": "vnc-desktop",  # Uses pre-configured Docker credentials
                "task": "Open browser and search for LangGraph",
            }
        )
        print(result.content[0].text)

asyncio.run(run_task())
```

## Supported Actions

The agent supports these Computer Use actions (mapped to VNC operations):

- `click_at(x, y)` - Click at normalized coordinates
- `double_click_at(x, y)` - Double-click at coordinates (for launching apps)
- `hover_at(x, y)` - Hover at coordinates
- `type_text_at(x, y, text, press_enter?, clear_before_typing?)` - Type text
- `key_combination(keys)` - Press keyboard shortcuts (e.g., "ctrl+a")
- `scroll_document(direction, magnitude)` - Scroll page
- `scroll_at(x, y, direction, magnitude)` - Scroll at location
- `drag_and_drop(x, y, destination_x, destination_y)` - Drag and drop
- `wait_5_seconds()` - Wait 5 seconds (useful for page loads)

### Excluded Actions (by default)

The following browser-specific actions are **excluded by default** because they require direct browser API access and cannot be reliably implemented via VNC mouse/keyboard simulation:

- `open_web_browser` - Use generic click/type actions to launch browsers from desktop
- `navigate` - Click URL bar and type URLs instead
- `go_back`, `go_forward` - Click browser navigation buttons instead
- `search` - Type in search boxes instead

You can override these exclusions by passing `excluded_actions=[]` when initializing the agent, though browser tasks are more reliably accomplished using the generic UI actions.

### Coordinate System

All coordinates from Gemini are **normalized to 0-999** (1000x1000 reference grid) and automatically converted to pixels based on the current screenshot dimensions.

## Credential Management

VNC server credentials are stored securely using a multi-tier credential store system. Credentials are **never passed as tool parameters** to avoid exposing them to LLMs.

### Credential Storage Backends

The system tries multiple storage backends in order (most secure first):

1. **OS Keyring** (encrypted, recommended for production)
   - macOS: Keychain
   - Windows: Credential Locker
   - Linux: Secret Service / GNOME Keyring
   - Requires: `pip install vnc-use[keyring]`

2. **~/.vnc_credentials** (Unix .netrc format)
   - Simple text file with `chmod 600` permissions
   - Standard Unix pattern, works everywhere
   - Format: `machine hostname\nlogin server\npassword secret`

3. **Environment Variables** (fallback for single-tenant)
   - `VNC_SERVER` and `VNC_PASSWORD`
   - Useful for Docker/testing
   - Only supports one VNC server

### Managing Credentials

**Set credentials for a VNC server:**
```bash
# Password will be prompted (recommended)
vnc-use-credentials set vnc-prod --server prod.example.com::5901

# Or specify password inline (⚠ visible in shell history)
vnc-use-credentials set vnc-desktop --server vnc-desktop::5901 --password vncpassword
```

**List configured servers:**
```bash
vnc-use-credentials list
```

**Get credentials:**
```bash
# Show server (password masked)
vnc-use-credentials get vnc-prod

# Show password in plain text
vnc-use-credentials get vnc-prod --show-password
```

**Delete credentials:**
```bash
vnc-use-credentials delete vnc-prod
```

### Using Credentials

Once credentials are stored, refer to VNC servers by **hostname only**:

```python
from vnc_use import VncUseAgent

# Credentials looked up automatically by hostname
agent = VncUseAgent(vnc_server="vnc-prod")
result = agent.run("Open browser and go to example.com")
```

For the MCP server, pass only the hostname:
```python
result = await client.call_tool(
    "execute_vnc_task",
    {
        "hostname": "vnc-desktop",  # Credentials from server-side store
        "task": "Open browser...",
    }
)
```

### Security Benefits

- ✓ Passwords never in LLM conversation logs
- ✓ Passwords never in tool parameters
- ✓ OS-level encryption (when using keyring)
- ✓ Multi-tenant support (hundreds of VNC servers)
- ✓ Credential rotation without code changes

## MCP Server

The VNC Computer Use agent can be run as a Model Context Protocol (MCP) server, enabling integration with MCP clients and providing streaming progress updates, observations, and screenshots during execution.

### Quick Start

**1. Start the services:**
```bash
# Configure your API key
cp .env.example .env
# Edit .env and set GOOGLE_API_KEY=your_google_api_key

# Start VNC desktop + MCP server
docker-compose up -d

# Verify services are running
docker-compose ps
# Should show:
#   vnc-use-test-desktop  - VNC desktop (ports 5901, 6901)
#   vnc-use-mcp-server    - MCP server (port 8001)
```

**2. Test the MCP server:**
```bash
# View VNC desktop in browser
open http://localhost:6901  # Password: vncpassword

# MCP server endpoint
curl http://localhost:8001/mcp
```

**3. Use from Python client:**
```python
import asyncio
from fastmcp import Client

async def main():
    async with Client("http://localhost:8001/mcp") as client:
        result = await client.call_tool(
            "execute_vnc_task",
            {
                "hostname": "vnc-desktop",  # Credentials from server-side store
                "task": "Open the browser and go to example.com",
                "step_limit": 20,
            }
        )
        print(f"Success: {result.content[0].text}")

asyncio.run(main())
```

**Note:** The Docker MCP server is pre-configured with credentials for `vnc-desktop` from environment variables. For production use with multiple VNC servers, use the credential management CLI.

### Starting the MCP Server

**With Docker (Recommended):**
```bash
# Start all services (VNC + MCP server)
docker-compose up -d

# MCP server available at http://localhost:8001/mcp
# VNC desktop accessible at vnc-desktop::5901 (inside Docker network)

# View logs
docker-compose logs -f mcp-server

# Stop services
docker-compose down
```

**Without Docker (Local VNC):**
```bash
# Start your own VNC server first, then:
export GOOGLE_API_KEY=your_google_api_key
export MCP_HOST=127.0.0.1  # localhost only (default)
export MCP_PORT=8001       # default port
uv run vnc-use-mcp

# MCP server available at http://localhost:8001/mcp
# Connect to your VNC server at localhost::5901
```

### MCP Tool: `execute_vnc_task`

The server exposes a single tool for executing VNC tasks.

**Parameters:**
- `hostname` (required): VNC server hostname for credential lookup (e.g., "vnc-desktop", "vnc-prod")
- `task` (required): Task description to execute
- `step_limit` (optional): Maximum steps (default: 40)
- `timeout` (optional): Timeout in seconds (default: 300)

**Security Note:** Credentials are looked up from the server-side credential store using the hostname. Never pass passwords as parameters - they would be exposed to the LLM.

**Returns:**
```json
{
  "success": true,
  "run_id": "20251010_153334_96982a39",
  "run_dir": "runs/20251010_153334_96982a39",
  "steps": 12,
  "error": null
}
```

### Streaming Updates

The MCP server streams real-time updates during execution:
- **Progress notifications**: Step count and current action
- **Model observations**: What the agent sees and thinks
- **Compressed screenshots**: 256px width images at each step
- **Action results**: Execution status of each action

### MCP Client Examples

**Basic Example - Browser Navigation:**
```python
import asyncio
import json
from fastmcp import Client

async def browse_website():
    """Navigate to a website and extract information."""
    async with Client("http://localhost:8001/mcp") as client:
        # Discover available tools
        tools = await client.list_tools()
        print(f"Available: {[t.name for t in tools]}")

        # Execute task
        result = await client.call_tool(
            "execute_vnc_task",
            {
                "hostname": "vnc-desktop",
                "task": "Open browser and go to python.org. Tell me the latest Python version shown on the homepage.",
                "step_limit": 20,
                "timeout": 120,
            }
        )

        # Parse result
        data = json.loads(result.content[0].text)
        print(f"\n{'='*70}")
        print(f"Success: {data['success']}")
        print(f"Steps taken: {data['steps']}")
        print(f"Run directory: {data['run_dir']}")
        if data.get('error'):
            print(f"Error: {data['error']}")
        print(f"{'='*70}")

        return data

asyncio.run(browse_website())
```

**Advanced Example - Web Scraping:**
```python
async def scrape_news():
    """Extract news headlines from a website."""
    async with Client("http://localhost:8001/mcp") as client:
        task = """
        Open a web browser and navigate to a tech news site.
        Find the top 3 news headlines on the page.
        Report the headlines as a numbered list.
        """

        result = await client.call_tool(
            "execute_vnc_task",
            {
                "hostname": "vnc-desktop",
                "task": task,
                "step_limit": 30,
            }
        )

        data = json.loads(result.content[0].text)

        # Check screenshots
        if data['success']:
            print(f"✓ Task completed in {data['steps']} steps")
            print(f"Check execution report:")
            print(f"  cat {data['run_dir']}/EXECUTION_REPORT.md")

asyncio.run(scrape_news())
```

**Credential Configuration:**

The Docker MCP server is pre-configured with credentials for `vnc-desktop` via environment variables. The credentials are automatically set up when the container starts.

For multiple VNC servers in production:
1. Configure credentials on the MCP server host using `vnc-use-credentials set`
2. Pass only the `hostname` parameter - credentials are looked up server-side
3. Never pass passwords in tool parameters - they would be exposed to the LLM

### Troubleshooting MCP Server

**Service not starting:**
```bash
# Check Docker services status
docker-compose ps

# View logs
docker-compose logs mcp-server
docker-compose logs vnc-desktop

# Restart services
docker-compose restart
```

**Connection refused:**
```bash
# Verify MCP server is listening
curl http://localhost:8001/mcp

# Check port is not already in use
lsof -i :8001

# Try rebuilding containers
docker-compose down
docker-compose up -d --build
```

**Task fails immediately:**
- Check GOOGLE_API_KEY is set correctly in `.env`
- Verify VNC desktop is running: `docker-compose ps`
- Test VNC access in browser: http://localhost:6901
- Check MCP server logs: `docker-compose logs mcp-server`

**Desktop state persists between runs:**
```bash
# Restart VNC desktop for clean state
docker-compose restart vnc-desktop
sleep 10  # Wait for desktop to be ready
```

**Accessing screenshots and reports:**
```bash
# Screenshots are saved in the runs/ directory (volume-mounted from container)
ls runs/
cat runs/LATEST_RUN_ID/EXECUTION_REPORT.md
```

### Security Considerations

- **Default binding**: The server binds to `127.0.0.1` (localhost only) by default
- **Network exposure**: Set `MCP_HOST=0.0.0.0` to expose externally (use with caution)
- **No authentication**: The server does not implement authentication (add reverse proxy if needed)
- **API keys**: GOOGLE_API_KEY is required and should be kept secure
- **VNC password**: Default is `vncpassword` - change in docker-compose.yml for production

### Human-in-the-Loop (HITL) Safety

The agent integrates Gemini's safety decision system with MCP's elicitation mechanism to enable **human approval for risky actions**:

**How it works:**
1. **Gemini detection**: When Gemini Computer Use model marks an action with `safety_decision.action = "require_confirmation"`, the agent pauses execution
2. **MCP elicitation**: The MCP server uses FastMCP's `ctx.elicit()` to request user approval
3. **User decision**: MCP client (Claude Desktop, IDE) prompts user to approve/decline/cancel
4. **Execution continues**: Only proceeds if user explicitly approves

**HITL is enabled by default** in MCP mode for safety. The system works at two levels:

- **Gemini-level safety**: Model detects risky operations (e.g., system commands, destructive actions)
- **MCP protocol-level**: Clients should implement additional approval UI per MCP specification

**Example risky actions that trigger HITL:**
- System-wide keyboard shortcuts (Ctrl+Alt+Delete)
- Actions marked as sensitive by Gemini's safety system
- Operations requiring explicit confirmation per model's judgment

**For CLI usage**, HITL uses LangGraph interrupts instead of MCP elicitation. Disable with `--no-hitl` flag if needed.

## Configuration

### Agent Options

```python
VncUseAgent(
    vnc_server="localhost::5901",      # VNC server address
    vnc_password=None,                 # VNC password (optional, see note below)
    screen_size=(1440, 900),           # Default size (auto-detected)
    excluded_actions=None,             # List of actions to exclude
    step_limit=40,                     # Max steps (guardrail)
    seconds_timeout=300,               # Wall-clock timeout
    hitl_mode=True,                    # Enable safety gates
    api_key=None,                      # Google API key (or use env var)
)
```

**Note on credentials:** For production use, configure credentials using the credential management system:
```bash
vnc-use-credentials set localhost --server localhost::5901 --password your_password
```
Then the agent can look up credentials automatically. Direct password parameters are supported for backward compatibility and simple use cases.

### CLI Options

```bash
vnc-use run \
  --vnc localhost::5901 \
  --password vncpassword \
  --task "Your task here" \
  --step-limit 50 \
  --timeout 600 \
  --no-hitl \
  --excluded-actions drag_and_drop \
  --verbose
```

## Run Artifacts

Each run creates a `runs/<run_id>/` directory containing:

- `EXECUTION_REPORT.md` - **Comprehensive markdown report with embedded screenshots, model observations, and execution timeline**
- `step_000_initial.png` - Initial screenshot
- `step_NNN_after.png` - Screenshots after each action
- `action_history.txt` - Text log of all actions and results
- `metadata.json` - Run metadata (task, duration, status, final state)

### Markdown Execution Reports

The `EXECUTION_REPORT.md` file provides a human-readable execution trace showing:

- Task description and run statistics
- Initial screenshot
- **For each step:**
  - Model's observations and reasoning
  - Proposed actions
  - Executed action with parameters
  - Success/error status
  - Screenshot showing the result
- Summary with total steps, success status, and error messages (if any)

This makes it easy to understand what the agent saw, what it tried to do, and why it made certain decisions.

## Testing

### Unit Tests

```bash
# VNC backend tests (with Docker VNC)
docker-compose up -d
uv run python tests/test_vnc_backend.py

# Gemini wrapper tests (no API needed)
uv run python tests/test_gemini_wrapper.py

# With real API
GOOGLE_API_KEY=key uv run python tests/test_gemini_wrapper.py --with-api
```

### End-to-End Tests

```bash
# Requires GOOGLE_API_KEY and running VNC
docker-compose up -d

# Simple desktop task
GOOGLE_API_KEY=key uv run python tests/test_e2e.py --test simple

# Browser task - Visit Mayflower blog and extract headlines
GOOGLE_API_KEY=key uv run python tests/test_browser_search.py

# Shell command task - Use terminal to check disk space
GOOGLE_API_KEY=key uv run python tests/test_shell_commands.py --test df

# Memory usage check
GOOGLE_API_KEY=key uv run python tests/test_shell_commands.py --test free

# MCP HTTP test - Get heise.de news via MCP server
python tests/test_mcp_http_heise.py
```

### Using pytest

```bash
# Install dev dependencies
uv sync --extra dev

# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_vnc_backend.py
```

## Project Structure

```
vnc-use/
├── src/vnc_use/
│   ├── __init__.py          # Public API
│   ├── agent.py             # LangGraph agent
│   ├── types.py             # Type definitions
│   ├── safety.py            # HITL handling
│   ├── logging_utils.py     # Run artifacts
│   ├── cli.py               # CLI entrypoint
│   ├── mcp_server.py        # MCP server implementation
│   ├── mcp_cli.py           # MCP server CLI entrypoint
│   ├── backends/
│   │   └── vnc.py           # VNC controller
│   └── planners/
│       └── gemini.py        # Gemini wrapper
├── tests/
│   ├── test_vnc_backend.py      # VNC tests
│   ├── test_gemini_wrapper.py   # Gemini tests
│   ├── test_e2e.py              # E2E tests
│   ├── test_browser_search.py   # Browser automation tests (Mayflower blog)
│   ├── test_shell_commands.py   # Shell command integration tests (df, free)
│   ├── test_mcp_server.py       # MCP server tests
│   └── test_mcp_http_heise.py   # MCP HTTP integration test (heise.de news)
├── docker-compose.yml           # Test VNC desktop
├── pyproject.toml               # Package configuration
├── LICENSE                      # MIT license
└── README.md                    # This file
```

## Requirements

- Python 3.10+
- Google API key (Gemini API)
- VNC server (or use docker-compose)

## Known Limitations

1. **Browser-optimized** - The Computer Use model is tuned for browser workflows; native desktop apps may need custom functions
2. **Sequential execution** - Function calls are executed one-by-one (parallelism possible future enhancement)
3. **HITL not interactive** - Current implementation logs but doesn't block on user input (TODO)
4. **No OCR fallback** - Purely vision-based grounding (by design)

## Model Information

- **Model:** `gemini-2.5-computer-use-preview-10-2025`
- **Tool:** Computer Use with `ENVIRONMENT_BROWSER`
- **Coordinate system:** Normalized 0-999 grid
- **Response format:** FunctionCalls with PNG screenshots

## Testing Guide

For detailed testing instructions, see [TESTING.md](TESTING.md)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Resources

- [Gemini Computer Use Docs](https://ai.google.dev/gemini-api/docs/computer-use)
- [LangGraph Documentation](https://docs.langchain.com/oss/python/langgraph/quickstart)
- [vncdotool Documentation](https://vncdotool.readthedocs.io/)
