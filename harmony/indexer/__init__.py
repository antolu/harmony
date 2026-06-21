from __future__ import annotations

from harmony.indexer._config import IndexerConfigAdmin, IndexerConfigCLI, SourceType

# Set the correct module name for better error messages and representation
for _cls in (IndexerConfigAdmin, IndexerConfigCLI):  # noqa: RUF067
    if hasattr(_cls, "__module__"):
        _cls.__module__ = "harmony.indexer"


__all__ = [
    "IndexerConfigAdmin",
    "IndexerConfigCLI",
    "SourceType",
]
