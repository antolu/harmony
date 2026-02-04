"""Elasticsearch configuration with per-language index support."""

from __future__ import annotations

import os
import typing
from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

LANGUAGE_ANALYZERS: typing.Final[dict[str, str]] = {
    "en": "english",
    "fr": "french",
    "de": "german",
    "es": "spanish",
    "it": "italian",
    "pt": "portuguese",
    "nl": "dutch",
    "ru": "russian",
    "ar": "arabic",
    "zh": "cjk",
    "ja": "cjk",
    "ko": "cjk",
}


class ImmutableESSettings(BaseModel):
    """Settings that cannot be changed after index creation."""

    shards: int = Field(1, description="Number of shards per index")
    replicas: int = Field(0, description="Number of replicas")


class MutableESSettings(BaseModel):
    """Settings that can be changed at runtime."""

    boost_title: float = Field(2.0, description="Title field boost")
    boost_content: float = Field(1.0, description="Content field boost")

    min_results_before_fallback: int = Field(
        5, description="Min results before searching other languages"
    )
    language_detection_confidence_threshold: float = Field(
        0.7, description="Min confidence for language detection (0.0-1.0)"
    )


class ESConfig(BaseSettings):
    """Elasticsearch configuration with per-language index support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ES_",
        extra="ignore",
    )

    host: str = "http://elasticsearch:9200"
    index_base_name: str = "harmony"
    languages: list[str] = ["en", "fr"]

    immutable: ImmutableESSettings = Field(default_factory=ImmutableESSettings)
    mutable: MutableESSettings = Field(default_factory=MutableESSettings)

    @classmethod
    def from_yaml(cls, yaml_path: Path | str) -> ESConfig:
        """Load configuration from YAML file."""
        with Path(yaml_path).open(encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # Explicitly override with environment variable if present
        # This is needed because kwargs in init take precedence over env vars
        if os.environ.get("ES_HOST"):
            data["host"] = os.environ["ES_HOST"]

        return cls(**data)

    def get_index_name(self, language: str) -> str:
        """Get index name for a specific language."""
        return f"{self.index_base_name}-{language}"

    def get_all_indices(self) -> list[str]:
        """Get all index names for configured languages."""
        return [self.get_index_name(lang) for lang in self.languages]

    def get_analyzer(self, language: str) -> str:
        """Get Elasticsearch analyzer for a language."""
        return LANGUAGE_ANALYZERS.get(language, "standard")

    def get_index_settings(self, language: str) -> dict[str, typing.Any]:
        """Get index settings for a specific language."""
        analyzer = self.get_analyzer(language)

        return {
            "settings": {
                "number_of_shards": self.immutable.shards,
                "number_of_replicas": self.immutable.replicas,
                "analysis": {
                    "analyzer": {
                        "default": {
                            "type": analyzer,
                        }
                    }
                },
            },
            "mappings": {
                "properties": {
                    "url": {"type": "keyword"},
                    "title": {"type": "text"},
                    "content": {"type": "text"},
                    "domain": {"type": "keyword"},
                    "path": {"type": "keyword"},
                    "depth": {"type": "integer"},
                    "crawled_at": {"type": "date"},
                    "file_path": {"type": "keyword"},
                    "language": {"type": "keyword"},
                }
            },
        }
