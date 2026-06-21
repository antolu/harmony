from __future__ import annotations

from harmony._mod_replace import replace_modname
from harmony.indexer._config import IndexerConfigAdmin, IndexerConfigCLI, SourceType
from harmony.indexer._core import (
    EmbedContext,
    RunIndexingContext,
    embed_and_upsert,
    make_stats_writer,
)
from harmony.indexer._pipeline import run_indexing
from harmony.indexer._sources import resolve_configs

__all__ = [
    "EmbedContext",
    "IndexerConfigAdmin",
    "IndexerConfigCLI",
    "RunIndexingContext",
    "SourceType",
    "embed_and_upsert",
    "make_stats_writer",
    "resolve_configs",
    "run_indexing",
]

for name in __all__:  # noqa: RUF067
    obj = globals()[name]
    replace_modname(obj, __name__)
