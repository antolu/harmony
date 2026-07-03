from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AdminSettings(BaseSettings):
    """Admin service configuration settings."""

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

    config_store: Literal["filesystem", "postgres"] = Field(
        default="filesystem",
        description="Admin config storage backend (read at startup)",
    )
    k8s_namespace: str = Field(
        default="harmony",
        description="Kubernetes namespace for the kubernetes job executor",
    )
    k8s_job_image: str = Field(
        default="harmony-api:latest",
        description="Container image used for Kubernetes job pods",
    )
    k8s_models_pvc_name: str = Field(
        default="models-pvc",
        description="PersistentVolumeClaim name for shared model storage",
    )
    k8s_data_pvc_name: str = Field(
        default="harmony-data",
        description="PersistentVolumeClaim name for shared crawl/index data storage",
    )

    crawler_output_path: Path | None = Field(
        default=None,
        alias="ADMIN_CRAWLER_OUTPUT_PATH",
        description="Default output directory for crawl jobs",
    )


settings = AdminSettings()
