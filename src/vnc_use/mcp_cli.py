"""CLI entrypoint for VNC Computer Use MCP server."""

import logging
import os

from .mcp_server import mcp


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def main() -> None:
    """Run the MCP server with streamable HTTP transport."""
    # Allow configuring host via environment variable for security
    # Default to localhost for local development, set MCP_HOST=0.0.0.0 to expose externally
    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_PORT", "8000"))

    mcp.run(
        transport="streamable-http",
        host=host,
        port=port,
        path="/mcp",
    )


if __name__ == "__main__":
    main()
