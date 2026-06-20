from __future__ import annotations

import contextlib
from pathlib import Path

import pydantic
from elasticsearch import Elasticsearch
from jsonargparse import ActionConfigFile, ArgumentParser
from pydantic import BaseModel, Field
from rich.console import Console

from harmony.config.elasticsearch import ESConfig
from harmony.providers.web_crawler.cli_index import EmbedContext, _embed_and_upsert


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


def _load_docs_from_es(es: Elasticsearch, *, index: str) -> list[tuple[str, str]]:
    docs: list[tuple[str, str]] = []
    response = es.search(
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
            response = es.scroll(scroll_id=scroll_id, scroll="2m")
        else:
            break

    if scroll_id:
        with contextlib.suppress(Exception):
            es.clear_scroll(scroll_id=scroll_id)

    return docs


def main() -> None:
    parser = ArgumentParser(
        description="Re-embed documents from ES and upsert to Qdrant"
    )
    parser.add_argument("--config", action=ActionConfigFile)
    parser.add_class_arguments(EmbedderConfig, nested_key="embedder")
    args = parser.parse_args()
    config = EmbedderConfig(**vars(args.embedder))
    console = Console()

    if config.es_config:
        es_cfg = ESConfig.from_yaml(Path(config.es_config))
        es_host = es_cfg.host
        languages = es_cfg.languages
        index_base_name = es_cfg.index_base_name
    else:
        es_host = config.es_host
        languages = config.languages
        index_base_name = config.index_base_name

    es = Elasticsearch([es_host])
    if not es.ping():
        console.print("[red]Cannot connect to Elasticsearch[/red]")
        return

    all_entries: list[dict[str, pydantic.JsonValue]] = []
    for lang in languages:
        index = f"{index_base_name}-{lang}"
        if not es.indices.exists(index=index):
            console.print(f"[yellow]Skipping missing index: {index}[/yellow]")
            continue
        docs = _load_docs_from_es(es, index=index)
        for url, content in docs:
            all_entries.append({"url": url, "_content": content})

    console.print(f"[green]Loaded {len(all_entries)} documents from ES[/green]")

    _embed_and_upsert(
        EmbedContext(
            all_entries=all_entries,
            qdrant_host=config.qdrant_host,
            qdrant_collection=config.qdrant_collection,
            embedding_model=config.embedding_model,
            batch_size=config.embedding_batch_size,
        )
    )


if __name__ == "__main__":
    main()
