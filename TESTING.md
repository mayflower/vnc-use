# Testing Guide

## Quick Start with Docker

### 1. Start the VNC Desktop Container

```bash
docker-compose up -d
```

This starts an Ubuntu desktop with XFCE and Chromium, accessible via VNC.

### 2. Access the Desktop

**Option A: Web Browser (noVNC)**
- Open http://localhost:6901
- Password: `vncpassword`
- Click "Connect"

**Option B: VNC Client**
- Connect to `localhost:5901`
- Password: `vncpassword`

### 3. Run the Tests

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

### 4. Test Descriptions

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

### 5. Stop the Container

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
