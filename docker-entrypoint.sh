#!/bin/bash
# Docker entrypoint script for MCP server
# Configures VNC credentials from environment variables before starting server

set -e

# Configure VNC credentials if environment variables are set
if [ -n "$VNC_SERVER" ] && [ -n "$VNC_PASSWORD" ]; then
    echo "Configuring VNC credentials from environment..."

    # Extract hostname from VNC_SERVER (e.g., "vnc-desktop::5901" -> "vnc-desktop")
    VNC_HOSTNAME=$(echo "$VNC_SERVER" | cut -d':' -f1)

    # Create .vnc_credentials file using netrc format
    mkdir -p /root
    cat > /root/.vnc_credentials <<EOF
machine ${VNC_HOSTNAME}
login ${VNC_SERVER}
password ${VNC_PASSWORD}
EOF

    # Set secure permissions
    chmod 600 /root/.vnc_credentials

    echo "✓ Configured credentials for hostname: ${VNC_HOSTNAME}"
else
    echo "⚠ VNC_SERVER and VNC_PASSWORD not set - credentials must be configured manually"
fi

# Start MCP server
exec "$@"
