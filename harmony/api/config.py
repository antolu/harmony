from __future__ import annotations

from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from harmony.config.elasticsearch import ESConfig


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Elasticsearch Configuration
    es_config_file: Path | None = None
    es_config: ESConfig = Field(default_factory=ESConfig)

    # LLM Configuration
    gemini_api_key: str
    llm_model: str = "gemini/gemini-3-flash-preview"

    # Ollama (optional)
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3"

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Search Configuration
    search_results_size: int = 10

    # Agentic Search Configuration
    agentic_max_refinement_rounds: int = 3
    agentic_max_query_variants: int = 4
    agentic_search_top_k: int = 10
    agentic_max_sources_returned: int = 10
    embedding_model: str = "text-embedding-3-small"

    # Document Cache Configuration
    document_cache_enabled: bool = True
    document_cache_ttl: int = 3600
    document_cache_max_size: int = 1000

    # MCP Server Configuration
    mcp_servers: list[dict[str, str | list[str] | dict[str, str]]] = []

    # Prompt Management
    dev_mode: bool = False
    prompts_dir: Path | None = None

    @model_validator(mode="after")
    def initialize_es_config(self) -> Settings:
        """Initialize ES config from file or environment."""
        if self.es_config_file and Path(self.es_config_file).exists():
            self.es_config = ESConfig.from_yaml(self.es_config_file)
        return self


settings = Settings()
