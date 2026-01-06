from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Elasticsearch
    es_host: str = "http://localhost:9200"
    es_index: str = "admin-eguide"

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


settings = Settings()
