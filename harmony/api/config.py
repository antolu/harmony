from __future__ import annotations

from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from harmony.config.elasticsearch import ESConfig


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

    gemini_api_key: str | None = Field(
        default=None,
        description="Gemini API key (required when using gemini/* models)",
    )
    openai_api_key: str | None = Field(
        default=None,
        description="OpenAI API key (required when using gpt-* models)",
    )
    anthropic_api_key: str | None = Field(
        default=None,
        description="Anthropic API key (required when using claude-* models)",
    )
    llm_model: str = Field(
        default="gemini/gemini-3-flash-preview",
        description="LLM model identifier (e.g., gemini/gemini-3-flash-preview, gpt-4, claude-3-5-sonnet-20241022, ollama_chat/llama3)",
    )

    ollama_host: str = Field(
        default="http://localhost:11434",
        description="Ollama server URL (only used when llm_model starts with ollama_chat/)",
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
    embedding_model: str = Field(
        default="ollama/qwen3-embedding:0.6b",
        description="Embedding model for vector search via litellm",
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
    qdrant_vector_size: int = Field(
        default=512,
        description="Embedding vector dimensions — must match the embedding model output (qwen3-embedding:0.6b = 512)",
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

    mcp_servers: list[dict[str, str | list[str] | dict[str, str]]] = Field(
        default=[],
        description="MCP (Model Context Protocol) server configurations for external tools",
    )

    dev_mode: bool = Field(
        default=False,
        description="Enable development mode (auto-reload prompts, verbose logging)",
    )
    prompts_dir: Path | None = Field(
        default=None,
        description="Custom directory for prompt templates (defaults to harmony/prompts)",
    )

    @model_validator(mode="after")
    def initialize_es_config(self) -> Settings:
        """Initialize ES config from file or environment."""
        if self.es_config_file and Path(self.es_config_file).exists():
            self.es_config = ESConfig.from_yaml(self.es_config_file)
        return self


settings = Settings()
