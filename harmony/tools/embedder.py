from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path

import pydantic
from jsonargparse import ActionConfigFile, ArgumentParser
from pydantic import BaseModel, Field
from rich.console import Console

from harmony.clients import ElasticsearchService, QdrantService
from harmony.core._elasticsearch_config import ESConfig
from harmony.indexer import EmbedContext, embed_and_upsert


class EmbedderConfig(BaseModel):
    es_host: str = Field("http://localhost:9200", description="Elasticsearch host")
    es_config: str | None = Field(None, description="Path to ES YAML config file")
    index_base_name: str = Field("harmony", description="Base name for ES indices")
    qdrant_host: str = Field("http://localhost:6333", description="Qdrant server URL")
    qdrant_collection: str = Field("harmony", description="Qdrant collection name")
    embedding_model: str = Field(
        "ollama/qwen3-embedding:0.6b", description="litellm embedding model"
    )
    embedding_batch_size: int = Field(64, description="Embedding batch size")
    languages: list[str] = Field(
        default_factory=lambda: ["en"], description="Languages to embed"
    )


async def _load_docs_from_es(
    es_service: ElasticsearchService, *, index: str
) -> list[tuple[str, str]]:
    docs: list[tuple[str, str]] = []
    response = await es_service.client.search(
        index=index,
        body={"query": {"match_all": {}}, "_source": ["url", "title", "content"]},
        scroll="2m",
        size=500,
    )
    scroll_id = response.get("_scroll_id")

    while True:
        hits = response["hits"]["hits"]
        if not hits:
            break
        for hit in hits:
            src = hit["_source"]
            url = src.get("url", "")
            content = f"{src.get('title', '')} {src.get('content', '')}".strip()
            if url:
                docs.append((url, content))
        if scroll_id:
            response = await es_service.client.scroll(scroll_id=scroll_id, scroll="2m")
        else:
            break

    if scroll_id:
        with contextlib.suppress(Exception):
            await es_service.client.clear_scroll(scroll_id=scroll_id)

    return docs


async def _run(config: EmbedderConfig, console: Console) -> None:
    if config.es_config:
        es_cfg = ESConfig.from_yaml(Path(config.es_config))
        es_host = es_cfg.host
        languages = es_cfg.languages
        index_base_name = es_cfg.index_base_name
    else:
        es_host = config.es_host
        languages = config.languages
        index_base_name = config.index_base_name

    es_service = ElasticsearchService(host=es_host)
    if not await es_service.health_check():
        console.print("[red]Cannot connect to Elasticsearch[/red]")
        return

    all_entries: list[dict[str, pydantic.JsonValue]] = []
    for lang in languages:
        index = f"{index_base_name}-{lang}"
        if not await es_service.index_exists(name=index):
            console.print(f"[yellow]Skipping missing index: {index}[/yellow]")
            continue
        docs = await _load_docs_from_es(es_service, index=index)
        for url, content in docs:
            all_entries.append({"url": url, "_content": content})

    console.print(f"[green]Loaded {len(all_entries)} documents from ES[/green]")

    qdrant_service = QdrantService(
        host=config.qdrant_host,
        collection=config.qdrant_collection,
        vector_size=512,  # TODO: Hardcoded for now, could make dynamic
    )

    await embed_and_upsert(
        EmbedContext(
            all_entries=all_entries,
            qdrant_service=qdrant_service,
            embedding_model=config.embedding_model,
            batch_size=config.embedding_batch_size,
        )
    )

    await es_service.close()


def main() -> None:
    parser = ArgumentParser(
        description="Re-embed documents from ES and upsert to Qdrant"
    )
    parser.add_argument("--config", action=ActionConfigFile)
    parser.add_class_arguments(EmbedderConfig, nested_key="embedder")
    args = parser.parse_args()
    config = EmbedderConfig(**vars(args.embedder))
    console = Console()
    asyncio.run(_run(config, console))


if __name__ == "__main__":
    main()
