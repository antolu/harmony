from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from harmony.core import ESConfig


class Settings(BaseSettings):
    """
    Harmony API configuration settings.

    Settings are loaded from environment variables (with or without .env file).
    All settings can be overridden via environment variables with matching names.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    es_config_file: Path | None = Field(
        default=None,
        description="Path to Elasticsearch YAML config file (optional, overrides individual ES settings)",
    )
    es_config: ESConfig = Field(
        default_factory=ESConfig,
        description="Elasticsearch configuration (per-language indices, analyzers, search strategy)",
    )

    api_host: str = Field(
        default="0.0.0.0",
        description="Host to bind the API server (0.0.0.0 = all interfaces)",
    )
    api_port: int = Field(
        default=8000,
        description="Port to bind the API server",
    )

    search_results_size: int = Field(
        default=10,
        description="Maximum number of search results to return per query",
    )

    agentic_max_refinement_rounds: int = Field(
        default=3,
        description="Maximum query refinement iterations for agentic search",
    )
    agentic_max_query_variants: int = Field(
        default=4,
        description="Maximum number of query variants to generate per refinement round",
    )
    agentic_search_top_k: int = Field(
        default=10,
        description="Top-K results to retrieve per query variant in agentic search",
    )
    agentic_max_sources_returned: int = Field(
        default=10,
        description="Maximum number of unique sources to return in agentic search final results",
    )
    ai_search_max_iterations: int = Field(
        default=3,
        description="Max /ai-search tool-calling iterations, including the final forced synthesis turn",
    )
    ai_search_source_token_budget: int = Field(
        default=12_000,
        description="Approximate token budget for source content the /ai-search model reasons over",
    )
    embedding_batch_size: int = Field(
        default=64,
        description="Number of documents to embed per litellm batch call",
    )
    qdrant_host: str = Field(
        default="http://localhost:6333",
        description="Qdrant server URL",
    )
    qdrant_collection: str = Field(
        default="harmony",
        description="Qdrant collection name for document vectors",
    )
    document_cache_enabled: bool = Field(
        default=True,
        description="Enable in-memory document caching for faster repeated access",
    )
    document_cache_ttl: int = Field(
        default=3600,
        description="Document cache TTL in seconds (1 hour default)",
    )
    document_cache_max_size: int = Field(
        default=1000,
        description="Maximum number of documents to cache in memory",
    )
    document_cache_backend: Literal["memory", "redis"] = Field(
        default="memory",
        description="Document cache backend (read at startup)",
    )
    job_executor: Literal["subprocess", "kubernetes"] = Field(
        default="subprocess",
        description="Job execution backend (read at startup)",
    )

    cors_allowed_origins_raw: str = Field(
        default="",
        alias="cors_allowed_origins",
        description="Allowed CORS origins. REQUIRED in production — API fails to start if empty. Comma-separated: http://localhost:3001,http://localhost:8080",
    )

    @property
    def cors_allowed_origins(self) -> list[str]:
        return [
            o.strip() for o in self.cors_allowed_origins_raw.split(",") if o.strip()
        ]

    dev_mode: bool = Field(
        default=False,
        description="Enable development mode (auto-reload prompts, verbose logging)",
    )

    @model_validator(mode="after")
    def initialize_es_config(self) -> Settings:
        """Initialize ES config from file or environment."""
        if self.es_config_file and Path(self.es_config_file).exists():
            self.es_config = ESConfig.from_yaml(self.es_config_file)
        return self
