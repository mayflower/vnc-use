# Dockerfile for VNC Computer Use MCP Server
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml /app/
COPY README.md /app/
COPY LICENSE /app/
COPY src/ /app/src/

# Install dependencies
RUN uv pip install --system -e .

# Create runs directory for artifacts
RUN mkdir -p /app/runs

# Expose MCP server port
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000

# Run MCP server
CMD ["python", "-m", "vnc_use.mcp_cli"]
