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


settings = Settings()
