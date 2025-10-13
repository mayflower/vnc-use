"""CLI for managing VNC credentials.

Provides commands to set, get, list, and delete VNC server credentials.
Credentials are stored securely using OS keyring, .netrc file, or environment variables.
"""

import argparse
import getpass
import sys

from .credential_store import get_default_store


def set_credentials(args: argparse.Namespace) -> int:
    """Set credentials for a VNC server hostname."""
    store = get_default_store()

    hostname = args.hostname
    server = args.server or hostname

    # Prompt for password if not provided
    if args.password:
        password = args.password
    else:
        password = getpass.getpass(f"VNC password for {hostname}: ")

    try:
        store.set(hostname, server, password)
        print(f"✓ Stored credentials for {hostname}")
        print(f"  Server: {server}")
        print(f"  Password: {'***' if password else '(none)'}")
        return 0
    except Exception as e:
        print(f"✗ Failed to store credentials: {e}", file=sys.stderr)
        return 1


def get_credentials(args: argparse.Namespace) -> int:
    """Get credentials for a VNC server hostname."""
    store = get_default_store()

    hostname = args.hostname

    credentials = store.get(hostname)
    if credentials:
        print(f"✓ Found credentials for {hostname}")
        print(f"  Server: {credentials.server}")
        if args.show_password:
            print(f"  Password: {credentials.password or '(none)'}")
        else:
            print(f"  Password: {'***' if credentials.password else '(none)'}")
        return 0
    print(f"✗ No credentials found for {hostname}", file=sys.stderr)
    return 1


def list_credentials(args: argparse.Namespace) -> int:
    """List all stored VNC server hostnames."""
    store = get_default_store()

    hostnames = store.list_hosts()
    if hostnames:
        print(f"Stored credentials for {len(hostnames)} host(s):")
        for hostname in hostnames:
            print(f"  - {hostname}")
        return 0
    print("No credentials stored")
    return 0


def delete_credentials(args: argparse.Namespace) -> int:
    """Delete credentials for a VNC server hostname."""
    store = get_default_store()

    hostname = args.hostname

    if store.delete(hostname):
        print(f"✓ Deleted credentials for {hostname}")
        return 0
    print(f"✗ No credentials found for {hostname}", file=sys.stderr)
    return 1


def main() -> int:
    """Main entry point for credentials CLI."""
    parser = argparse.ArgumentParser(
        description="Manage VNC server credentials",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Set credentials (password prompted)
  vnc-use credentials set vnc-desktop --server vnc-desktop::5901

  # Set credentials with password (not recommended - visible in shell history)
  vnc-use credentials set vnc-prod --server prod.example.com::5901 --password secret

  # Get credentials
  vnc-use credentials get vnc-desktop

  # List all configured hosts
  vnc-use credentials list

  # Delete credentials
  vnc-use credentials delete vnc-desktop

Credential Storage:
  Credentials are stored securely using (in order of preference):
  1. OS Keyring (macOS Keychain, Windows Credential Locker, Linux Secret Service)
  2. ~/.vnc_credentials file (Unix .netrc format, chmod 600)
  3. Environment variables VNC_SERVER and VNC_PASSWORD (fallback)
""",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    subparsers.required = True

    # Set command
    set_parser = subparsers.add_parser("set", help="Set credentials for a hostname")
    set_parser.add_argument("hostname", help="VNC server hostname (e.g., vnc-desktop, vnc-prod)")
    set_parser.add_argument(
        "--server",
        help="Full VNC server address (default: hostname). Example: hostname::5901",
    )
    set_parser.add_argument(
        "--password",
        help="VNC password (prompted if not provided). WARNING: visible in shell history",
    )
    set_parser.set_defaults(func=set_credentials)

    # Get command
    get_parser = subparsers.add_parser("get", help="Get credentials for a hostname")
    get_parser.add_argument("hostname", help="VNC server hostname")
    get_parser.add_argument(
        "--show-password",
        action="store_true",
        help="Show password in plain text (default: masked)",
    )
    get_parser.set_defaults(func=get_credentials)

    # List command
    list_parser = subparsers.add_parser("list", help="List all configured hostnames")
    list_parser.set_defaults(func=list_credentials)

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete credentials for a hostname")
    delete_parser.add_argument("hostname", help="VNC server hostname")
    delete_parser.set_defaults(func=delete_credentials)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
