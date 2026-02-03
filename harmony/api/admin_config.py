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
    es_host: str = Field(
        default="http://localhost:9200",
        description="Elasticsearch host for reset operations",
    )
    es_state_index: str = Field(
        default="harmony-crawl-state",
        description="Crawl state index name",
    )
    es_index_base_name: str = Field(
        default="harmony",
        description="Base name for search indices",
    )

    novnc_url: str = Field(
        default="http://localhost:6080",
        description="noVNC server URL for SSO authentication",
    )

    crawler_output_path: Path = Field(
        default=Path("output"),
        description="Default output directory for crawl jobs",
    )


settings = AdminSettings()
