from __future__ import annotations

import typing
from pathlib import Path

from pydantic import BaseModel, Field

SourceType = typing.Literal["disk", "elasticsearch"]


class IndexerConfig(BaseModel):
    """Indexer configuration loaded from YAML or CLI."""

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
            "'disk': Read from metadata.jsonl files in --data-dir. "
            "'elasticsearch': Query from state index (requires --state-index)."
        ),
    )
    state_index: str = Field(
        "harmony-crawl-state",
        description="Crawl state index name (for deletion sync or source=elasticsearch)",
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
    es_host: str = Field(
        "http://localhost:9200",
        description="Elasticsearch host (ignored if es_config is provided)",
    )
    index_base_name: str = Field(
        "harmony",
        description="Base name for indices (ignored if es_config is provided)",
    )
    verbose: int = Field(0, description="Verbosity level (0=INFO, 1+=DEBUG)")
