"""Credential storage for VNC server authentication.

Provides pluggable credential stores with multiple backend implementations:
- NetrcStore: Uses standard .netrc file format (simple, Unix standard)
- KeyringStore: Uses OS keyring (encrypted, secure)
- EnvironmentStore: Fallback to environment variables (single-tenant)

Each store keys credentials by VNC server hostname/address.
"""

import json
import logging
import os
from abc import ABC, abstractmethod


logger = logging.getLogger(__name__)


class VNCCredentials:
    """VNC connection credentials."""

    def __init__(self, server: str, password: str | None = None):
        """Initialize VNC credentials.

        Args:
            server: VNC server address (e.g., "localhost::5901")
            password: VNC password (optional)
        """
        self.server = server
        self.password = password

    def __repr__(self) -> str:
        return (
            f"VNCCredentials(server={self.server!r}, password={'***' if self.password else None})"
        )


class CredentialStore(ABC):
    """Abstract base class for credential storage backends."""

    @abstractmethod
    def get(self, hostname: str) -> VNCCredentials | None:
        """Get credentials for a VNC server hostname.

        Args:
            hostname: VNC server hostname or address (e.g., "vnc-prod-01.example.com")

        Returns:
            VNCCredentials if found, None otherwise
        """

    @abstractmethod
    def set(self, hostname: str, server: str, password: str | None = None) -> None:
        """Store credentials for a VNC server hostname.

        Args:
            hostname: VNC server hostname or address
            server: Full VNC server address (e.g., "hostname::5901")
            password: VNC password (optional)
        """

    @abstractmethod
    def delete(self, hostname: str) -> bool:
        """Delete credentials for a hostname.

        Args:
            hostname: VNC server hostname or address

        Returns:
            True if credentials were deleted, False if not found
        """

    @abstractmethod
    def list_hosts(self) -> list[str]:
        """List all stored hostnames.

        Returns:
            List of hostname strings
        """


class NetrcStore(CredentialStore):
    """Credential store using .netrc file format.

    Uses standard Unix .netrc format for storing credentials.
    File location: ~/.vnc_credentials (or custom path)

    Format:
        machine hostname
        login username
        password secret

    Note: Relies on file permissions (chmod 600) for security.
    """

    def __init__(self, file_path: str | None = None):
        """Initialize netrc credential store.

        Args:
            file_path: Path to netrc file (default: ~/.vnc_credentials)
        """
        if file_path is None:
            file_path = "~/.vnc_credentials"
        self.file_path = os.path.expanduser(file_path)

    def get(self, hostname: str) -> VNCCredentials | None:
        """Get credentials from netrc file."""
        try:
            import netrc

            n = netrc.netrc(self.file_path)
            auth = n.authenticators(hostname)
            if auth:
                login, account, password = auth
                # For VNC, we store server address in login field
                server = login if login else hostname
                return VNCCredentials(server=server, password=password)
            return None
        except FileNotFoundError:
            logger.debug(f"Netrc file not found: {self.file_path}")
            return None
        except netrc.NetrcParseError as e:
            logger.error(f"Failed to parse netrc file: {e}")
            return None

    def set(self, hostname: str, server: str, password: str | None = None) -> None:
        """Store credentials in netrc file.

        Note: This appends to the file. Manual editing required to update existing entries.
        """
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.file_path) or ".", exist_ok=True)

        # Append to netrc file
        with open(self.file_path, "a") as f:
            f.write(f"\nmachine {hostname}\n")
            f.write(f"login {server}\n")
            if password:
                f.write(f"password {password}\n")

        # Set secure permissions
        os.chmod(self.file_path, 0o600)
        logger.info(f"Stored credentials for {hostname} in {self.file_path}")

    def delete(self, hostname: str) -> bool:
        """Delete credentials from netrc file."""
        try:
            # Read entire file
            with open(self.file_path) as f:
                lines = f.readlines()

            # Filter out the machine entry
            new_lines = []
            skip = False
            for line in lines:
                if line.strip().startswith(f"machine {hostname}"):
                    skip = True
                    continue
                if skip and line.strip().startswith("machine "):
                    skip = False
                if not skip:
                    new_lines.append(line)

            # Write back
            with open(self.file_path, "w") as f:
                f.writelines(new_lines)

            logger.info(f"Deleted credentials for {hostname}")
            return True
        except FileNotFoundError:
            return False

    def list_hosts(self) -> list[str]:
        """List all hostnames in netrc file."""
        try:
            import netrc

            n = netrc.netrc(self.file_path)
            return list(n.hosts.keys())
        except (FileNotFoundError, netrc.NetrcParseError):
            return []


class KeyringStore(CredentialStore):
    """Credential store using OS keyring (encrypted).

    Uses Python keyring library to store credentials in OS credential stores:
    - macOS: Keychain
    - Windows: Credential Locker
    - Linux: Secret Service / GNOME Keyring

    Credentials are stored as JSON under service name "vnc-use".
    """

    SERVICE_NAME = "vnc-use"

    def __init__(self):
        """Initialize keyring credential store."""
        try:
            import keyring

            self.keyring = keyring
        except ImportError as e:
            raise ImportError(
                "keyring package required for KeyringStore. Install with: pip install keyring"
            ) from e

    def get(self, hostname: str) -> VNCCredentials | None:
        """Get credentials from OS keyring."""
        try:
            creds_json = self.keyring.get_password(self.SERVICE_NAME, hostname)
            if creds_json:
                creds = json.loads(creds_json)
                return VNCCredentials(
                    server=creds.get("server", hostname), password=creds.get("password")
                )
            return None
        except Exception as e:
            logger.error(f"Failed to get credentials from keyring: {e}")
            return None

    def set(self, hostname: str, server: str, password: str | None = None) -> None:
        """Store credentials in OS keyring."""
        try:
            creds = {"server": server, "password": password}
            self.keyring.set_password(self.SERVICE_NAME, hostname, json.dumps(creds))
            logger.info(f"Stored credentials for {hostname} in OS keyring")
        except Exception as e:
            logger.error(f"Failed to store credentials in keyring: {e}")
            raise

    def delete(self, hostname: str) -> bool:
        """Delete credentials from OS keyring."""
        try:
            self.keyring.delete_password(self.SERVICE_NAME, hostname)
            logger.info(f"Deleted credentials for {hostname} from keyring")
            return True
        except self.keyring.errors.PasswordDeleteError:
            return False
        except Exception as e:
            logger.error(f"Failed to delete credentials from keyring: {e}")
            return False

    def list_hosts(self) -> list[str]:
        """List all hostnames in keyring.

        Note: Not all keyring backends support enumeration.
        Returns empty list if enumeration not supported.
        """
        # Most keyring backends don't support enumeration
        logger.warning("Keyring enumeration not supported by most backends")
        return []


class EnvironmentStore(CredentialStore):
    """Credential store using environment variables (fallback for single-tenant).

    Reads credentials from environment variables:
    - VNC_SERVER: VNC server address
    - VNC_PASSWORD: VNC password

    This is the simplest store but only supports one VNC server.
    Suitable for single-tenant deployments or testing.
    """

    def get(self, hostname: str) -> VNCCredentials | None:
        """Get credentials from environment variables.

        Ignores hostname parameter - always returns same credentials.
        """
        server = os.getenv("VNC_SERVER")
        password = os.getenv("VNC_PASSWORD")

        if server:
            logger.debug(f"Using VNC credentials from environment (hostname={hostname} ignored)")
            return VNCCredentials(server=server, password=password)

        return None

    def set(self, hostname: str, server: str, password: str | None = None) -> None:
        """Not supported for environment store."""
        raise NotImplementedError("EnvironmentStore does not support set()")

    def delete(self, hostname: str) -> bool:
        """Not supported for environment store."""
        raise NotImplementedError("EnvironmentStore does not support delete()")

    def list_hosts(self) -> list[str]:
        """Return single entry if environment variables are set."""
        server = os.getenv("VNC_SERVER")
        return [server] if server else []


class ChainedStore(CredentialStore):
    """Credential store that tries multiple backends in order.

    Attempts to get credentials from each store in the chain until one succeeds.
    Write operations use the first writable store.

    Typical chain: KeyringStore → NetrcStore → EnvironmentStore
    """

    def __init__(self, stores: list[CredentialStore]):
        """Initialize chained credential store.

        Args:
            stores: List of credential stores to try in order
        """
        self.stores = stores

    def get(self, hostname: str) -> VNCCredentials | None:
        """Try each store until credentials are found."""
        for store in self.stores:
            creds = store.get(hostname)
            if creds:
                logger.debug(f"Found credentials for {hostname} in {store.__class__.__name__}")
                return creds
        return None

    def set(self, hostname: str, server: str, password: str | None = None) -> None:
        """Store in first writable store."""
        for store in self.stores:
            if not isinstance(store, EnvironmentStore):
                store.set(hostname, server, password)
                return
        raise RuntimeError("No writable credential store available")

    def delete(self, hostname: str) -> bool:
        """Delete from all stores."""
        deleted = False
        for store in self.stores:
            try:
                if store.delete(hostname):
                    deleted = True
            except NotImplementedError:
                continue
        return deleted

    def list_hosts(self) -> list[str]:
        """List hosts from all stores."""
        all_hosts = set()
        for store in self.stores:
            all_hosts.update(store.list_hosts())
        return sorted(all_hosts)


def get_default_store() -> CredentialStore:
    """Get default credential store with fallback chain.

    Tries stores in this order:
    1. KeyringStore (OS-encrypted, secure) - if keyring available
    2. NetrcStore (standard Unix format) - if file exists
    3. EnvironmentStore (fallback for testing)

    Returns:
        ChainedStore with available backends
    """
    stores: list[CredentialStore] = []

    # Try KeyringStore first (most secure)
    try:
        stores.append(KeyringStore())
        logger.debug("Using KeyringStore (OS-encrypted)")
    except ImportError:
        logger.debug("KeyringStore not available (install keyring package)")

    # Add NetrcStore
    stores.append(NetrcStore())
    logger.debug("Using NetrcStore (~/.vnc_credentials)")

    # Add EnvironmentStore as final fallback
    stores.append(EnvironmentStore())
    logger.debug("Using EnvironmentStore fallback")

    return ChainedStore(stores)
