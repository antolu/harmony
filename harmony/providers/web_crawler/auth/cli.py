from __future__ import annotations

import argparse
import asyncio
import sys
import typing
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table

from harmony.core import BackendSessionWriter, SessionData
from harmony.providers.web_crawler.auth.config import AuthConfig
from harmony.providers.web_crawler.auth.registry import AuthProviderRegistry

if TYPE_CHECKING:
    import yaml  # noqa: F401

    from harmony.core import SessionWriter


console = Console()


class _PgSessionWriter:
    """Direct sync psycopg session writer for CLI use when no backend is available."""

    def __init__(self, database_url: str) -> None:
        import psycopg  # noqa: PLC0415

        self._conn = psycopg.connect(database_url, autocommit=True)

    def load(self) -> list[SessionData]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT subdomain, provider_type, domain_pattern, cookies, headers, "
            "storage_state_file, created_at, expires_at FROM auth_sessions"
        )
        columns = [desc[0] for desc in cur.description]
        rows: list[SessionData] = []
        for row in cur.fetchall():
            entry = dict(zip(columns, row, strict=False))
            if entry.get("created_at"):
                entry["created_at"] = entry["created_at"].isoformat()
            if entry.get("expires_at"):
                entry["expires_at"] = entry["expires_at"].isoformat()
            rows.append(typing.cast(SessionData, entry))
        return rows

    def upsert(self, session: SessionData) -> None:
        self._conn.execute(
            """
            INSERT INTO auth_sessions
                (subdomain, provider_type, domain_pattern, cookies, headers, storage_state_file, created_at, expires_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (subdomain) DO UPDATE SET
                provider_type = EXCLUDED.provider_type,
                domain_pattern = EXCLUDED.domain_pattern,
                cookies = EXCLUDED.cookies,
                headers = EXCLUDED.headers,
                storage_state_file = EXCLUDED.storage_state_file,
                expires_at = EXCLUDED.expires_at
            """,
            (
                session.get("subdomain", ""),
                session.get("provider_type", ""),
                session.get("domain_pattern", ""),
                session.get("cookies", {}),
                session.get("headers", {}),
                session.get("storage_state_file"),
                session.get("created_at"),
                session.get("expires_at"),
            ),
        )

    def invalidate(self, subdomain: str) -> None:
        self._conn.execute(
            "DELETE FROM auth_sessions WHERE subdomain = %s", (subdomain,)
        )

    def clear_all(self) -> None:
        self._conn.execute("DELETE FROM auth_sessions")

    def close(self) -> None:
        self._conn.close()


def _make_cli_session_writer() -> SessionWriter | None:
    """Create a session writer appropriate for CLI context."""
    import os  # noqa: PLC0415

    backend_url = os.environ.get("HARMONY_BACKEND_URL")
    if backend_url:
        return BackendSessionWriter(backend_url)

    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return _PgSessionWriter(database_url)

    return None


def load_auth_config(config_path: Path | None = None) -> AuthConfig:
    """Load auth config from file or defaults."""
    if config_path and config_path.exists():
        import yaml  # noqa: PLC0415

        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if "auth" in data:
            return AuthConfig(**data["auth"])
    return AuthConfig()


def cmd_auth_login(
    provider_name: str,
    config_path: Path | None = None,
    url: str | None = None,
) -> int:
    """
    Perform interactive login for an SSO provider.

    Args:
        provider_name: Name of the SSO provider (e.g., 'cern-sso')
        config_path: Path to harmony config file
        url: Optional URL to authenticate against (uses provider's login_url if not specified)

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    console.print(f"\n[bold]Authenticating with {provider_name}...[/bold]\n")

    auth_config = load_auth_config(config_path)
    session_writer = _make_cli_session_writer()
    registry = AuthProviderRegistry(auth_config, session_writer=session_writer)

    provider = registry.get_provider_by_name(provider_name)
    if not provider:
        console.print(f"[red]Error: Provider '{provider_name}' not found[/red]")
        console.print("\nAvailable interactive providers:")
        for p in registry.get_interactive_providers():
            if hasattr(p, "config") and hasattr(p.config, "name"):
                console.print(f"  - {p.config.name}")  # type: ignore[attr-defined]
        return 1

    if not provider.is_interactive():
        console.print(
            f"[red]Error: Provider '{provider_name}' is not interactive[/red]"
        )
        return 1

    # Perform authentication
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        session = loop.run_until_complete(provider.authenticate("manual-login", url))
    except TimeoutError:
        console.print("\n[red]✗ Authentication timed out[/red]")
        return 1
    except Exception as e:
        console.print(f"\n[red]✗ Authentication failed: {e}[/red]")
        return 1

    console.print("\n[green]✓ Authentication successful![/green]")

    subdomain = session.subdomain if hasattr(session, "subdomain") else provider_name
    registry.store_session(subdomain, session)

    if hasattr(provider, "config") and hasattr(provider.config, "storage_state_file"):
        console.print(
            f"Session saved to: {provider.config.storage_state_file}"  # type: ignore[attr-defined]
        )
    console.print(f"Cookies obtained: {len(session.cookies)}")

    return 0


def cmd_auth_status(config_path: Path | None = None) -> int:
    """
    Show authentication status for all providers.

    Args:
        config_path: Path to harmony config file

    Returns:
        Exit code
    """
    auth_config = load_auth_config(config_path)
    session_writer = _make_cli_session_writer()
    registry = AuthProviderRegistry(auth_config, session_writer=session_writer)
    registry.load_sessions()

    console.print("\n[bold]Authentication Status[/bold]\n")

    # Providers table
    table = Table(title="Configured Providers")
    table.add_column("Type", style="cyan")
    table.add_column("Name/Domains", style="green")
    table.add_column("Status", style="yellow")

    MAX_DOMAINS_DISPLAY = 2
    for provider in registry.get_providers():
        provider_type = provider.provider_type
        domain_patterns = [
            p.pattern for p in provider.domain_patterns[:MAX_DOMAINS_DISPLAY]
        ]
        domains = ", ".join(domain_patterns)
        if len(provider._domain_patterns) > MAX_DOMAINS_DISPLAY:  # noqa: SLF001
            domains += (
                f" (+{len(provider._domain_patterns) - MAX_DOMAINS_DISPLAY} more)"  # noqa: SLF001
            )

        # Check status
        if provider.is_interactive():
            if (
                hasattr(provider, "has_valid_storage_state")
                and provider.has_valid_storage_state()
            ):
                status = "[green]✓ Authenticated[/green]"
            else:
                status = "[yellow]⚠ Not authenticated[/yellow]"
        else:
            status = "[green]✓ Ready[/green]"

        name = (
            getattr(provider.config, "name", "") if hasattr(provider, "config") else ""
        )
        table.add_row(provider_type, f"{name}\n{domains}", status)

    console.print(table)

    # Sessions table
    sessions = registry.get_sessions()
    if sessions:
        sessions_table = Table(title="\nActive Sessions")
        sessions_table.add_column("Subdomain", style="cyan")
        sessions_table.add_column("Provider", style="green")
        sessions_table.add_column("Created", style="yellow")
        sessions_table.add_column("Expires", style="red")

        for subdomain, session in sessions.items():
            expires = (
                session.expires_at.strftime("%Y-%m-%d %H:%M")
                if session.expires_at
                else "Never"
            )
            sessions_table.add_row(
                subdomain,
                session.provider_type,
                session.created_at.strftime("%Y-%m-%d %H:%M"),
                expires,
            )

        console.print(sessions_table)
    else:
        console.print("\n[dim]No active sessions[/dim]")

    return 0


def _clear_single_provider_sessions(
    registry: typing.Any, provider: typing.Any, session_writer: typing.Any
) -> None:
    registry.load_sessions()
    sessions = registry.get_sessions()
    for subdomain, session in sessions.items():
        if (
            provider.matches_domain(subdomain)
            or session.provider_type == provider.provider_type
        ):
            session_writer.invalidate(subdomain)


def _clear_all_sessions(session_writer: typing.Any) -> None:
    if hasattr(session_writer, "clear_all"):
        session_writer.clear_all()
    else:
        entries = session_writer.load()
        for entry in entries:
            session_writer.invalidate(entry.get("subdomain", ""))
    console.print("[green]✓ Cleared all sessions[/green]")


def cmd_auth_clear(
    provider_name: str | None = None,
    config_path: Path | None = None,
) -> int:
    """
    Clear authentication sessions.

    Args:
        provider_name: Clear only sessions for this provider (None = all)
        config_path: Path to harmony config file

    Returns:
        Exit code
    """
    auth_config = load_auth_config(config_path)
    session_writer = _make_cli_session_writer()

    if provider_name:
        registry = AuthProviderRegistry(auth_config, session_writer=session_writer)
        provider = registry.get_provider_by_name(provider_name)
        if not provider:
            console.print(
                f"[red]Error: Auth provider '{provider_name}' not found[/red]"
            )
            return 1

        if session_writer:
            _clear_single_provider_sessions(registry, provider, session_writer)
            console.print(f"[green]✓ Cleared sessions for {provider_name}[/green]")

        if hasattr(provider, "config") and hasattr(
            provider.config, "storage_state_file"
        ):
            storage_file = provider.config.storage_state_file  # type: ignore[attr-defined]
            if storage_file and storage_file.exists():
                storage_file.unlink()
                console.print(
                    f"[green]✓ Cleared storage state for {provider_name}[/green]"
                )
        return 0

    if session_writer:
        _clear_all_sessions(session_writer)

    for provider_config in auth_config.providers:
        if hasattr(provider_config, "storage_state_file"):
            storage_file = provider_config.storage_state_file
            if storage_file and storage_file.exists():
                storage_file.unlink()
                console.print(f"[green]✓ Cleared {storage_file}[/green]")

    return 0


def _setup_parser() -> argparse.ArgumentParser:
    """Set up CLI argument parser."""
    parser = argparse.ArgumentParser(description="Harmony Crawler Authentication")
    parser.add_argument("--config", type=Path, help="Path to harmony config file")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # login command
    login_parser = subparsers.add_parser("login", help="Perform interactive login")
    login_parser.add_argument("provider", help="SSO provider name (e.g., cern-sso)")
    login_parser.add_argument("--url", help="URL to authenticate against")

    # status command
    subparsers.add_parser("status", help="Show authentication status")

    # clear command
    clear_parser = subparsers.add_parser("clear", help="Clear authentication sessions")
    clear_parser.add_argument("--provider", help="Clear only this provider's sessions")

    return parser


def main() -> int:
    """CLI entry point for harmony-auth command."""
    parser = _setup_parser()
    args = parser.parse_args()

    if args.command == "login":
        return cmd_auth_login(args.provider, args.config, args.url)
    if args.command == "status":
        return cmd_auth_status(args.config)
    if args.command == "clear":
        return cmd_auth_clear(args.provider, args.config)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
