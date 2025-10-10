# vnc-use

**LangGraph agent for Computer Use via VNC with Gemini 2.5**

A Python package that enables autonomous desktop interaction through VNC using Google's Gemini 2.5 Computer Use model. The agent runs a tight *observe → propose → act* loop, grounding actions directly from screenshots without OCR or template matching.

## Features

- **Direct screenshot grounding** - No OCR, no template matching (per Computer Use design)
- **Generic desktop automation** - Works with any VNC-accessible desktop
- **Safety-first HITL** - Optional human-in-the-loop gates for risky actions
- **Coordinate denormalization** - Handles any screen resolution
- **LangGraph orchestration** - Stateless vision architecture for efficient token usage
- **Structured logging** - Full run artifacts with screenshots at each step
- **Markdown execution reports** - Human-readable reports with embedded screenshots showing what the agent saw, thought, and did

## Architecture

The agent implements a continuous observe-propose-act loop:

```
Task
  ↓
Observe (VNC Screenshot)
  ↓
Propose (Gemini Computer Use)
  ↓
HITL Gate (if confirmation needed)
  ↓
Act (Execute on VNC)
  ↓
Loop until done or timeout
```

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
```

## Quick Start

### 1. Start VNC Desktop (Docker)

```bash
docker-compose up -d
# Accessible at http://localhost:6901 (password: vncpassword)
```

### 2. Set API Key

```bash
export GOOGLE_API_KEY=your_google_api_key
```

### 3. Run a Task

**CLI:**
```bash
uv run vnc-use run --task "Open a browser and search for LangGraph"
```

**Python API:**
```python
from vnc_use import VncUseAgent

agent = VncUseAgent(
    vnc_server="localhost::5901",
    vnc_password="vncpassword",
    step_limit=40,
    seconds_timeout=300,
    hitl_mode=True,  # Enable safety confirmations
)

result = agent.run("Open the browser and navigate to google.com")
print(f"Success: {result['success']}")
print(f"Artifacts: {result['run_dir']}")
```

## Supported Actions

The agent supports these Computer Use actions (mapped to VNC operations):

- `click_at(x, y)` - Click at normalized coordinates
- `hover_at(x, y)` - Hover at coordinates
- `type_text_at(x, y, text, press_enter?, clear_before_typing?)` - Type text
- `key_combination(keys)` - Press keyboard shortcuts (e.g., "ctrl+a")
- `scroll_document(direction, magnitude)` - Scroll page
- `scroll_at(x, y, direction, magnitude)` - Scroll at location
- `drag_and_drop(x, y, destination_x, destination_y)` - Drag and drop
- `open_web_browser` - No-op placeholder

### Coordinate System

All coordinates from Gemini are **normalized to 0-999** (1000x1000 reference grid) and automatically converted to pixels based on the current screenshot dimensions.

## Configuration

### Agent Options

```python
VncUseAgent(
    vnc_server="localhost::5901",      # VNC server address
    vnc_password=None,                 # VNC password (optional)
    screen_size=(1440, 900),           # Default size (auto-detected)
    excluded_actions=None,             # List of actions to exclude
    step_limit=40,                     # Max steps (guardrail)
    seconds_timeout=300,               # Wall-clock timeout
    hitl_mode=True,                    # Enable safety gates
    api_key=None,                      # Google API key (or use env var)
)
```

### CLI Options

```bash
vnc-use run \
  --vnc localhost::5901 \
  --password vncpassword \
  --task "Your task here" \
  --step-limit 50 \
  --timeout 600 \
  --no-hitl \
  --excluded-actions open_web_browser \
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

### End-to-End Test

```bash
# Requires GOOGLE_API_KEY and running VNC
docker-compose up -d
GOOGLE_API_KEY=key uv run python tests/test_e2e.py --test simple
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
│   ├── backends/
│   │   └── vnc.py           # VNC controller
│   └── planners/
│       └── gemini.py        # Gemini wrapper
├── tests/
│   ├── test_vnc_backend.py      # VNC tests
│   ├── test_gemini_wrapper.py   # Gemini tests
│   ├── test_e2e.py              # E2E tests
│   └── test_browser_search.py   # Browser automation tests
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
