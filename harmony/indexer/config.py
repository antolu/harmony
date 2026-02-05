from __future__ import annotations

import typing
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import SettingsConfigDict

SourceType = typing.Literal["disk", "elasticsearch"]


class IndexerConfig(BaseModel):
    """Indexer configuration loaded from YAML or CLI."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ES_",
        extra="ignore",
    )

    data_dir: Path = Field(
        ...,
        description=(
            "Directory containing crawled files (required for both sources). "
            "For 'disk' source: Also contains metadata.jsonl files. "
            "For 'elasticsearch' source: Only used for file path resolution."
        ),
    )
    source: SourceType = Field(
        "disk",
        description=(
            "Source for metadata entries (default: disk). "
            "'disk': Read from metadata.jsonl files. "
            "'elasticsearch': Query ES state index."
        ),
    )

    sync_deletions: bool = Field(
        default=False,
        description="Sync deletions from crawl state to content index",
    )
    missing_threshold: int = Field(
        3,
        description="Number of crawls before deletion (for deletion sync)",
    )
    batch_size: int = Field(
        100,
        description="Bulk indexing batch size",
    )
    es_config: Path | None = Field(
        None,
        description="Path to Elasticsearch YAML config file (for connection/index settings)",
    )
    es_host: str | None = Field(
        None,
        description="Elasticsearch host URL (overrides es_config if both provided)",
    )
    index_base_name: str = Field(
        "harmony",
        description="Base name for indices (ignored if es_config is provided)",
    )
    languages: list[str] | None = Field(
        None,
        description="Languages to index (overrides es_config/DB if provided)",
    )
    verbose: int = Field(0, description="Verbosity level (0=INFO, 1+=DEBUG)")
    skip_embedding: bool = Field(
        default=False,
        description="Skip embedding generation and Qdrant upsert (index to ES only)",
    )
    qdrant_host: str = Field(
        "http://localhost:6333",
        description="Qdrant server URL for vector upsert",
    )
    qdrant_collection: str = Field(
        "harmony",
        description="Qdrant collection name for document vectors",
    )
    embedding_model: str = Field(
        "ollama/qwen3-embedding:0.6b",
        description="litellm embedding model identifier",
    )
    embedding_batch_size: int = Field(
        64,
        description="Number of documents to embed per litellm batch call",
    )
