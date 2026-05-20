from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AdminSettings(BaseSettings):
    """Admin API configuration settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="ADMIN_",
    )

    host: str = Field(
        default="0.0.0.0",
        description="Host to bind the admin API server",
    )
    port: int = Field(
        default=8001,
        description="Port to bind the admin API server",
    )

    config_storage_path: Path = Field(
        default=Path("/data/configs"),
        description="Directory to store configuration files",
    )
    job_log_path: Path = Field(
        default=Path("/data/logs"),
        description="Directory to store job logs",
    )
    harmony_backend_url: str = Field(
        default="http://harmony-api:8000",
        alias="HARMONY_BACKEND_URL",
    )

    novnc_url: str = Field(
        default="http://harmony-api:6080",
        description="noVNC server URL for SSO authentication (served by API)",
    )

    crawler_output_path: Path = Field(
        default=Path("output"),
        description="Default output directory for crawl jobs",
    )


settings = AdminSettings()
