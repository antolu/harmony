from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from harmony.db.connection import get_async_pool
from harmony.db.repositories import AuthSessionsRepo

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

        try:
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()
        except Exception:
            logger.exception("Failed to start SSO browser")
            raise

        if result.returncode != 0:
            msg = f"Failed to start container: {stderr.decode().strip()}"
            raise RuntimeError(msg)

        container_id = stdout.decode().strip()
        self.active_containers[session_id] = container_id

        vnc_info = {
            "container_id": container_id,
            "container_name": container_name,
            "vnc_host": container_name,
            "vnc_port": "5900",
        }

        logger.info(
            f"Started SSO browser container: {container_id} for session {session_id}"
        )
        return vnc_info

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
            msg = f"No active container for session {session_id}"
            raise ValueError(msg)

        container_id = self.active_containers[session_id]

        empty: dict[str, str | list] = {
            "provider": provider,
            "created_at": datetime.now(UTC).isoformat(),
            "cookies": [],
        }

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

        try:
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()
        except Exception:
            logger.exception("Failed to extract session data")
            return empty

        if result.returncode != 0:
            logger.error(f"Failed to extract cookies: {stderr.decode().strip()}")
            return empty

        session_data = json.loads(stdout.decode().strip())
        session_data["provider"] = provider
        session_data["created_at"] = datetime.now(UTC).isoformat()
        return session_data

    async def save_session(
        self, session_id: str, provider: str, storage_state_file: Path | None = None
    ) -> None:
        """Extract session data and persist to database.

        Args:
            session_id: Session identifier
            provider: Auth provider name
            storage_state_file: Optional path to Playwright browser state file
        """
        session_data = await self.extract_session_data(session_id, provider)

        subdomain = provider
        raw_cookies: str | list = session_data.get("cookies", [])
        cookies: dict[str, str] = (
            {c.get("name", ""): c.get("value", "") for c in raw_cookies}
            if isinstance(raw_cookies, list)
            else {}
        )

        pool = await get_async_pool()
        await AuthSessionsRepo(pool).upsert(
            subdomain,
            {
                "provider_type": provider,
                "domain_pattern": "",
                "cookies": cookies,
                "headers": {},
                "storage_state_file": str(storage_state_file)
                if storage_state_file
                else None,
                "created_at": str(
                    session_data.get("created_at", datetime.now(UTC).isoformat())
                ),
                "expires_at": None,
            },
        )
        logger.info(f"Saved session data for {provider} to database")

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
        cmd = [
            "docker",
            "ps",
            "-aq",
            "--filter",
            f"name={container_name}",
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except Exception:
            logger.exception("Failed to get container ID")
            return None
        container_id = result.stdout.strip()
        return container_id if container_id else None

    async def _stop_container(self, container_id: str) -> None:
        """Stop and remove a container.

        Args:
            container_id: Container ID to stop
        """
        try:
            await asyncio.create_subprocess_exec(
                "docker", "stop", container_id, stdout=asyncio.subprocess.DEVNULL
            )
            await asyncio.create_subprocess_exec(
                "docker", "rm", container_id, stdout=asyncio.subprocess.DEVNULL
            )
        except Exception:
            logger.exception(f"Failed to stop container {container_id}")
        else:
            logger.info(f"Stopped and removed container: {container_id}")


# Global instance
sso_handler = SSOHandler()
