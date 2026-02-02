from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class SSOHandler:
    """Manages noVNC browser containers for SSO authentication."""

    def __init__(
        self,
        docker_network: str = "harmony",
        container_prefix: str = "harmony-sso",
        session_storage_path: Path | None = None,
    ) -> None:
        self.docker_network = docker_network
        self.container_prefix = container_prefix
        self.session_storage_path = session_storage_path or Path("/data/auth-sessions")
        self.active_containers: dict[str, str] = {}  # session_id -> container_id

    async def start_browser_session(
        self, session_id: str, provider: str, login_url: str
    ) -> dict[str, str]:
        """Start a containerized browser with VNC for SSO login.

        Args:
            session_id: Unique session identifier
            provider: Auth provider name
            login_url: URL to navigate to for login

        Returns:
            Dictionary with container_id and vnc_port
        """
        container_name = f"{self.container_prefix}-{session_id}"

        # Check if container already exists
        existing = await self._get_container_id(container_name)
        if existing:
            logger.warning(f"Container {container_name} already exists, removing it")
            await self._stop_container(existing)

        # Start the browser container
        try:
            # Run sso-browser container
            cmd = [
                "docker",
                "run",
                "-d",
                "--name",
                container_name,
                "--network",
                self.docker_network,
                "-e",
                f"LOGIN_URL={login_url}",
                "-e",
                f"PROVIDER={provider}",
                "-v",
                f"{self.session_storage_path}:/sessions",
                "harmony-sso-browser",
            ]

            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()

            if result.returncode != 0:
                raise RuntimeError(
                    f"Failed to start container: {stderr.decode().strip()}"
                )

            container_id = stdout.decode().strip()
            self.active_containers[session_id] = container_id

            # Get VNC port (container port 5900)
            vnc_info = {
                "container_id": container_id,
                "container_name": container_name,
                "vnc_host": container_name,  # accessible via docker network
                "vnc_port": "5900",
            }

            logger.info(
                f"Started SSO browser container: {container_id} for session {session_id}"
            )
            return vnc_info

        except Exception as e:
            logger.exception(f"Failed to start SSO browser: {e}")
            raise

    async def stop_browser_session(self, session_id: str) -> None:
        """Stop and remove the browser container for a session.

        Args:
            session_id: Session identifier
        """
        if session_id not in self.active_containers:
            logger.warning(f"No active container for session {session_id}")
            return

        container_id = self.active_containers.pop(session_id)
        await self._stop_container(container_id)

    async def extract_session_data(
        self, session_id: str, provider: str
    ) -> dict[str, str | list]:
        """Extract cookies and session data from browser container.

        Args:
            session_id: Session identifier
            provider: Auth provider name

        Returns:
            Dictionary with session data (cookies, storage, etc.)
        """
        if session_id not in self.active_containers:
            raise ValueError(f"No active container for session {session_id}")

        container_id = self.active_containers[session_id]

        try:
            # Execute command in container to extract browser session data
            # This assumes chromium stores data in a known location
            cmd = [
                "docker",
                "exec",
                container_id,
                "python3",
                "-c",
                """
import json
import sqlite3
from pathlib import Path

# Chromium cookie database path
cookie_db = Path.home() / '.config/chromium/Default/Cookies'

cookies = []
if cookie_db.exists():
    conn = sqlite3.connect(str(cookie_db))
    cursor = conn.cursor()
    cursor.execute('SELECT host_key, name, value, path, expires_utc FROM cookies')
    for row in cursor.fetchall():
        cookies.append({
            'domain': row[0],
            'name': row[1],
            'value': row[2],
            'path': row[3],
            'expirationDate': row[4]
        })
    conn.close()

print(json.dumps({'cookies': cookies}))
""",
            ]

            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()

            if result.returncode != 0:
                logger.error(f"Failed to extract cookies: {stderr.decode().strip()}")
                # Return empty session data if extraction fails
                return {
                    "provider": provider,
                    "created_at": datetime.now(UTC).isoformat(),
                    "cookies": [],
                }

            session_data = json.loads(stdout.decode().strip())
            session_data["provider"] = provider
            session_data["created_at"] = datetime.now(UTC).isoformat()

            return session_data

        except Exception as e:
            logger.exception(f"Failed to extract session data: {e}")
            # Return basic session data
            return {
                "provider": provider,
                "created_at": datetime.now(UTC).isoformat(),
                "cookies": [],
            }

    async def save_session(
        self, session_id: str, provider: str, session_path: Path
    ) -> None:
        """Extract session data and save to file.

        Args:
            session_id: Session identifier
            provider: Auth provider name
            session_path: Path to save session data
        """
        session_data = await self.extract_session_data(session_id, provider)

        # Ensure directory exists
        session_path.parent.mkdir(parents=True, exist_ok=True)

        # Save to file
        session_path.write_text(json.dumps(session_data, indent=2))
        logger.info(f"Saved session data to {session_path}")

    async def cleanup_all_sessions(self) -> None:
        """Stop and remove all active SSO browser containers."""
        for session_id in list(self.active_containers.keys()):
            await self.stop_browser_session(session_id)

    async def _get_container_id(self, container_name: str) -> str | None:
        """Get container ID by name.

        Args:
            container_name: Container name

        Returns:
            Container ID if exists, None otherwise
        """
        try:
            cmd = [
                "docker",
                "ps",
                "-aq",
                "--filter",
                f"name={container_name}",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            container_id = result.stdout.strip()
            return container_id if container_id else None
        except Exception as e:
            logger.exception(f"Failed to get container ID: {e}")
            return None

    async def _stop_container(self, container_id: str) -> None:
        """Stop and remove a container.

        Args:
            container_id: Container ID to stop
        """
        try:
            # Stop container
            await asyncio.create_subprocess_exec(
                "docker", "stop", container_id, stdout=asyncio.subprocess.DEVNULL
            )
            # Remove container
            await asyncio.create_subprocess_exec(
                "docker", "rm", container_id, stdout=asyncio.subprocess.DEVNULL
            )
            logger.info(f"Stopped and removed container: {container_id}")
        except Exception as e:
            logger.exception(f"Failed to stop container {container_id}: {e}")


# Global instance
sso_handler = SSOHandler()
