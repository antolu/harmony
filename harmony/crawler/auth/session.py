from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class AuthSession:
    """Represents an authenticated session for a subdomain."""

    provider_type: str
    subdomain: str  # Full subdomain (e.g., "guides.web.cern.ch")
    domain_pattern: str  # Pattern that matched this subdomain
    created_at: datetime
    expires_at: datetime | None = None

    # Credentials to apply to requests
    cookies: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)

    # For Playwright SSO - reference to storage state file
    storage_state_file: Path | None = None

    def is_expired(self) -> bool:
        """Check if session has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def to_dict(self) -> dict:
        """Serialize session to dictionary."""
        return {
            "provider_type": self.provider_type,
            "subdomain": self.subdomain,
            "domain_pattern": self.domain_pattern,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "cookies": self.cookies,
            "headers": self.headers,
            "storage_state_file": (
                str(self.storage_state_file) if self.storage_state_file else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict) -> AuthSession:
        """Deserialize session from dictionary."""
        return cls(
            provider_type=data["provider_type"],
            subdomain=data["subdomain"],
            domain_pattern=data["domain_pattern"],
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=(
                datetime.fromisoformat(data["expires_at"])
                if data.get("expires_at")
                else None
            ),
            cookies=data.get("cookies", {}),
            headers=data.get("headers", {}),
            storage_state_file=(
                Path(data["storage_state_file"])
                if data.get("storage_state_file")
                else None
            ),
        )
