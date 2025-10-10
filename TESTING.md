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
# Simple desktop task
export GOOGLE_API_KEY=your_key
docker-compose up -d
uv run python tests/test_e2e.py --test simple

# Browser search task
uv run python tests/test_browser_search.py
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

### 4. Stop the Container

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
