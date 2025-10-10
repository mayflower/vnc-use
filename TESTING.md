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

### 3. Run the VNC Backend Tests

```bash
# Test coordinate denormalization only (no VNC required)
uv run python test_vnc_backend.py --skip-connection

# Test with the Docker VNC desktop (using default settings)
uv run python test_vnc_backend.py

# Or specify VNC server explicitly
uv run python test_vnc_backend.py --vnc localhost::5901 --password vncpassword
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
