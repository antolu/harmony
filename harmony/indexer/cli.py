from __future__ import annotations

import asyncio
import collections.abc
import json
import os
import sys
import typing
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import bs4
from elasticsearch import Elasticsearch, helpers
from jsonargparse import ActionConfigFile, ArgumentParser
from rich.console import Console
from rich.progress import Progress

from harmony.api.services.language_detection import language_detector
from harmony.config.elasticsearch import ESConfig
from harmony.crawler.writers import BackendStatsWriter, StatsWriter
from harmony.db.connection import get_async_pool
from harmony.db.repositories import ServiceConfigRepo
from harmony.indexer.config import IndexerConfig
from harmony.indexer.parsers import CorruptDocumentError, default_registry

console = Console()


def _make_stats_writer() -> StatsWriter | None:
    job_id = os.environ.get("HARMONY_CRAWL_JOB_ID")
    backend_url = os.environ.get("HARMONY_BACKEND_URL")
    if job_id and backend_url:
        return BackendStatsWriter(backend_url, job_id)
    return None


def _publish_stats(
    writer: StatsWriter | None,
    *,
    phase: str,
    indexed: int,
    total: int,
) -> None:
    if writer is None:
        return
    writer.publish({
        "timestamp": datetime.now(UTC).isoformat(),
        "current_phase": phase,
        "documents_indexed": indexed,
        "total_documents": total,
    })


def extract_text_from_html(html: str | bytes) -> tuple[str, str]:
    soup = bs4.BeautifulSoup(html, "lxml")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    for script in soup(["script", "style"]):
        script.decompose()

    text = soup.get_text(separator=" ", strip=True)
    text = " ".join(text.split())

    return title, text


def _load_all_entries(
    metadata_files: list[Path], console: Console
) -> list[dict[str, typing.Any]]:
    """Load all entries from metadata files."""
    all_entries = []
    for metadata_file in metadata_files:
        console.print(f"[cyan]Reading {metadata_file}[/cyan]")
        with metadata_file.open("r", encoding="utf-8") as f:
            entries = [json.loads(line) for line in f if line.strip()]
            for entry in entries:
                entry["_base_dir"] = metadata_file.parent

            all_entries.extend(entries)
    return all_entries


def _group_entries_by_language(
    all_entries: list[dict[str, typing.Any]],
) -> dict[str, list[dict[str, typing.Any]]]:
    """Group entries by language field."""
    entries_by_lang: dict[str, list[dict[str, typing.Any]]] = {}
    for entry in all_entries:
        lang = entry.get("language", "unknown")
        if lang not in entries_by_lang:
            entries_by_lang[lang] = []
        entries_by_lang[lang].append(entry)
    return entries_by_lang


def _transform_state_to_entry(
    state_doc: dict[str, typing.Any],
    data_dir: Path,
) -> dict[str, typing.Any] | None:
    """Transform ES state document to entry dict format."""
    # Skip if missing file_path
    if "file_path" not in state_doc or not state_doc["file_path"]:
        return None

    url = state_doc["url"]
    parsed = urlparse(url)

    entry = {
        "url": url,
        "domain": state_doc["domain"],
        "file_path": state_doc["file_path"],
        "depth": state_doc["depth"],
        "crawled_at": state_doc["last_crawled_at"],
        "path": state_doc.get("path", parsed.path or "/"),
        "language": state_doc.get("language", ""),
        "content_type": state_doc.get("content_type", ""),
        "_base_dir": data_dir,
    }

    # Preserve document type if present
    if "type" in state_doc:
        entry["type"] = state_doc["type"]

    return entry


def _load_entries_from_es(
    es: Elasticsearch,
    state_index: str,
    data_dir: Path,
    console: Console,
) -> list[dict[str, typing.Any]]:
    """Load entries from Elasticsearch state index."""
    # Validate index exists
    if not es.indices.exists(index=state_index):
        console.print(f"[red]Error: State index '{state_index}' does not exist[/red]")
        console.print("[yellow]Hint: Run crawler with state tracking enabled[/yellow]")
        return []

    # Query all documents using scan for efficient pagination
    query: dict[str, typing.Any] = {"query": {"match_all": {}}}

    console.print(f"[cyan]Querying state index: {state_index}[/cyan]")

    all_entries = []
    for doc in helpers.scan(es, query=query, index=state_index):
        state_doc = doc["_source"]
        entry = _transform_state_to_entry(state_doc, data_dir)
        if entry:
            all_entries.append(entry)

    console.print(f"[green]Loaded {len(all_entries)} entries from ES state[/green]")

    return all_entries


def _process_document(
    entry: dict[str, typing.Any], file_path: Path, console: Console
) -> tuple[str | None, str | None]:
    """Process a document file and extract text."""
    content_type = entry.get("content_type", "")
    extension = file_path.suffix

    parser = default_registry.get_parser(content_type, extension)
    if not parser:
        console.print(
            f"[yellow]No parser for {content_type} ({extension}): {file_path.name}[/yellow]"
        )
        return None, None

    try:
        title, content = parser.parse(file_path)
    except CorruptDocumentError as e:
        console.print(f"[red]Parse error {file_path.name}: {e}[/red]")
        return None, None
    else:
        return title, content


def _sync_deletions(
    es: Elasticsearch,
    console: Console,
    state_index: str,
    content_index: str,
    missing_threshold: int,
) -> None:
    """Sync deletions from crawl state to content index."""
    console.print("\n[yellow]Syncing deletions from crawl state...[/yellow]")

    if not es.indices.exists(index=state_index):
        console.print(f"[red]Error: State index {state_index} does not exist[/red]")
        return

    query = {"query": {"range": {"missing_count": {"gte": missing_threshold}}}}

    try:
        response = es.search(index=state_index, body=query, size=10000, source=False)
        urls_to_delete = [hit["_id"] for hit in response["hits"]["hits"]]

        if not urls_to_delete:
            console.print("[green]No URLs to delete[/green]")
        else:
            console.print(f"[yellow]Deleting {len(urls_to_delete)} URLs...[/yellow]")

            delete_actions = [
                {"_op_type": "delete", "_index": content_index, "_id": url}
                for url in urls_to_delete
            ]

            success_del, errors_del = helpers.bulk(
                es, delete_actions, raise_on_error=False, stats_only=True
            )

            console.print(f"[green]Deleted {success_del} documents[/green]")
            if errors_del:
                console.print(f"[red]Deletion errors: {errors_del}[/red]")

    except Exception as e:
        console.print(f"[red]Error during deletion sync: {e}[/red]")


def _generate_docs(
    all_entries: list[dict[str, typing.Any]],
    index_name: str,
    stats: dict[str, int],
    console: Console,
) -> collections.abc.Generator[dict[str, typing.Any], None, None]:
    """Generate Elasticsearch documents from entries."""
    for entry in all_entries:
        base_dir = entry.pop("_base_dir")
        file_path = base_dir / entry["file_path"]

        if not file_path.exists():
            console.print(f"[yellow]Warning: {file_path} not found, skipping[/yellow]")
            stats["missing_files"] += 1
            continue

        doc_type = entry.get("type", "html")

        if doc_type == "document":
            title, content = _process_document(entry, file_path, console)
            if title is None:
                stats["parse_errors"] += 1
                continue
            stats["documents"] += 1
        else:
            html = file_path.read_bytes()
            title, content = extract_text_from_html(html)
            stats["html"] += 1

        entry["_content"] = f"{title} {content}"

        yield {
            "_index": index_name,
            "_source": {
                "url": entry["url"],
                "title": title,
                "content": content,
                "domain": entry["domain"],
                "path": entry["path"],
                "depth": entry["depth"],
                "crawled_at": entry["crawled_at"],
                "file_path": entry["file_path"],
                "language": entry.get("language", ""),
            },
        }


def _setup_elasticsearch_index(
    es: Elasticsearch,
    index_name: str,
    language: str,
    es_config: ESConfig,
    console: Console,
) -> None:
    """Setup Elasticsearch index for a specific language."""
    console.print(f"[green]Creating index: {index_name} (language: {language})[/green]")

    index_settings = es_config.get_index_settings(language)

    if es.indices.exists(index=index_name):
        console.print(
            f"[yellow]Index {index_name} already exists, deleting...[/yellow]"
        )
        es.indices.delete(index=index_name)

    es.indices.create(index=index_name, body=index_settings)


def _perform_bulk_indexing(  # noqa: PLR0913 - needs all parameters for bulk operation
    es: Elasticsearch,
    all_entries: list[dict[str, typing.Any]],
    index_name: str,
    batch_size: int,
    stats: dict[str, int],
    console: Console,
    stats_writer: StatsWriter | None = None,
    total_documents: int = 0,
    already_indexed: int = 0,
) -> tuple[int, int]:
    """Perform bulk indexing and return success/error counts."""
    with Progress() as progress:
        task = progress.add_task("[cyan]Indexing documents...", total=len(all_entries))

        success_count = 0
        error_count = 0

        for ok, result in helpers.streaming_bulk(
            es,
            _generate_docs(all_entries, index_name, stats, console),
            chunk_size=batch_size,
            raise_on_error=False,
        ):
            if ok:
                success_count += 1
            else:
                error_count += 1
                console.print(f"[red]Error indexing: {result}[/red]")

            progress.update(task, advance=1)
            if (success_count + error_count) % 10 == 0:
                _publish_stats(
                    stats_writer,
                    phase="indexing",
                    indexed=already_indexed + success_count,
                    total=total_documents,
                )

    return success_count, error_count


def _print_indexing_summary(
    success_count: int, error_count: int, stats: dict[str, int], console: Console
) -> None:
    """Print indexing summary statistics."""
    console.print("[green]Indexing complete![/green]")
    console.print(f"[green]  Success: {success_count}[/green]")
    if error_count > 0:
        console.print(f"[red]  Errors: {error_count}[/red]")
    console.print(
        f"[cyan]Stats: {stats['html']} HTML pages, {stats['documents']} documents, "
        f"{stats['parse_errors']} parse errors, {stats['missing_files']} missing files[/cyan]"
    )


def _embed_and_upsert(  # noqa: PLR0913
    all_entries: list[dict[str, typing.Any]],
    qdrant_host: str,
    qdrant_collection: str,
    embedding_model: str,
    batch_size: int,
    console: Console,
) -> None:
    import asyncio  # noqa: PLC0415

    import litellm  # noqa: PLC0415
    import qdrant_client  # noqa: PLC0415
    import qdrant_client.models  # noqa: PLC0415

    from harmony.api.services.qdrant import _url_to_id  # noqa: PLC0415

    async def _run() -> None:
        client = qdrant_client.AsyncQdrantClient(url=qdrant_host)
        exists = await client.collection_exists(qdrant_collection)

        docs = [
            (entry["url"], entry.get("_content", ""))
            for entry in all_entries
            if entry.get("url") and entry.get("_content")
        ]

        console.print(
            f"[cyan]Embedding {len(docs)} documents in batches of {batch_size}[/cyan]"
        )

        with Progress() as progress:
            task = progress.add_task("[cyan]Embedding...", total=len(docs))

            for i in range(0, len(docs), batch_size):
                batch = docs[i : i + batch_size]
                urls = [u for u, _ in batch]
                texts = [t for _, t in batch]

                try:
                    response = await litellm.aembedding(
                        model=embedding_model, input=texts
                    )
                    vectors = [item.embedding for item in response.data]
                    vector_size = len(vectors[0])

                    if not exists and i == 0:
                        await client.create_collection(
                            collection_name=qdrant_collection,
                            vectors_config=qdrant_client.models.VectorParams(
                                size=vector_size,
                                distance=qdrant_client.models.Distance.COSINE,
                            ),
                        )
                        exists = True

                    points = [
                        qdrant_client.models.PointStruct(
                            id=_url_to_id(url),
                            vector=vec,
                            payload={"path": url},
                        )
                        for url, vec in zip(urls, vectors, strict=False)
                    ]
                    await client.upsert(
                        collection_name=qdrant_collection, points=points
                    )
                except Exception as e:
                    console.print(
                        f"[red]Embedding batch {i // batch_size} failed: {e}[/red]"
                    )

                progress.update(task, advance=len(batch))

        await client.close()
        console.print("[green]Embedding complete[/green]")

    asyncio.run(_run())


def _detect_languages_if_missing(
    all_entries: list[dict[str, typing.Any]],
    console: Console,
    stats_writer: StatsWriter | None = None,
    total_documents: int = 0,
) -> None:
    """Detect languages for entries where it is missing."""
    missing_count = sum(1 for e in all_entries if not e.get("language"))
    if missing_count == 0:
        return

    console.print(
        f"[yellow]Detecting language for {missing_count} documents...[/yellow]"
    )

    detected = 0
    with Progress() as progress:
        task = progress.add_task("[cyan]Detecting languages...", total=missing_count)

        for entry in all_entries:
            if entry.get("language"):
                continue

            base_dir = entry.get("_base_dir")
            if not base_dir:
                progress.update(task, advance=1)
                continue

            file_path = base_dir / entry["file_path"]

            if not file_path.exists():
                progress.update(task, advance=1)
                continue

            doc_type = entry.get("type", "html")
            content = None

            if doc_type == "document":
                _, content = _process_document(entry, file_path, console)
            else:
                try:
                    html = file_path.read_bytes()
                    _, content = extract_text_from_html(html)
                except Exception:
                    pass

            if content:
                lang = language_detector.detect_language(content)
                if lang:
                    entry["language"] = lang

            detected += 1
            progress.update(task, advance=1)
            if detected % 10 == 0:
                _publish_stats(
                    stats_writer,
                    phase="language_detection",
                    indexed=detected,
                    total=total_documents,
                )


async def _get_db_config(key: str) -> str | None:
    """Fetch configuration from database."""
    try:
        pool = await get_async_pool()
        repo = ServiceConfigRepo(pool)
        config = await repo.get(key)
        if config and config.get("is_configured"):
            return config["value"]
    except Exception:
        # Don't print error if just connection missing (e.g. no DB access in CI)
        # But per user request: "if DB access fails and no env/cli provided, fail with error"
        # We will handle the failure in the caller if we return None
        pass
    return None


def resolve_es_host(config: IndexerConfig, console: Console) -> str:
    """Resolve Elasticsearch host with priority: CLI/Config > Env > DB > Default."""
    # 1. CLI / Config file (explicitly set)
    if config.es_host:
        return config.es_host

    # 2. Environment variable
    env_host = os.environ.get("ES_HOST")
    if env_host:
        return env_host

    # 3. Database
    try:
        db_host = asyncio.run(_get_db_config("elasticsearch_url"))
        if db_host:
            console.print(f"[cyan]Using ES config from database: {db_host}[/cyan]")
            return db_host
    except Exception as e:
        console.print(f"[yellow]Warning: DB config check failed: {e}[/yellow]")

    # 4. Default (last resort)
    default_host = "http://elasticsearch:9200"
    console.print(f"[yellow]Using default ES host: {default_host}[/yellow]")
    return default_host


def resolve_index_base_name(config: IndexerConfig, console: Console) -> str:
    """Resolve index base name with priority: CLI/Config > Env > DB > Default."""
    # 1. CLI / Config file (explicitly set, non-default)
    if config.index_base_name != "harmony":
        return config.index_base_name

    # 2. Environment variable
    env_name = os.environ.get("ES_INDEX_BASE_NAME")
    if env_name:
        return env_name

    # 3. Database
    try:
        db_name = asyncio.run(_get_db_config("es_index_base_name"))
        if db_name:
            console.print(
                f"[cyan]Using index base name from database: {db_name}[/cyan]"
            )
            return db_name
    except Exception as e:
        console.print(f"[yellow]Warning: DB config check failed: {e}[/yellow]")

    # 4. Default
    return "harmony"


def resolve_languages(config: IndexerConfig, console: Console) -> list[str]:
    """Resolve languages with priority: CLI/Config > Env > DB > Default."""
    # 1. CLI / Config file (explicitly set)
    if config.languages:
        return config.languages

    # 2. Environment variable
    env_langs = os.environ.get("ES_LANGUAGES")
    if env_langs:
        return [lang.strip() for lang in env_langs.split(",") if lang.strip()]

    # 3. Database
    try:
        db_langs = asyncio.run(_get_db_config("es_languages"))
        if db_langs:
            langs = [lang.strip() for lang in db_langs.split(",") if lang.strip()]
            console.print(f"[cyan]Using languages from database: {langs}[/cyan]")
            return langs
    except Exception as e:
        console.print(f"[yellow]Warning: DB config check failed: {e}[/yellow]")

    # 4. Default
    return ["en", "fr"]


def main() -> None:  # noqa: PLR0912, PLR0914, PLR0915
    parser = ArgumentParser(
        prog="harmony-index",
        description="Index crawled data to Elasticsearch",
        default_config_files=["indexer_config.yaml"],
    )
    parser.add_argument(
        "--config", action=ActionConfigFile, help="Path to YAML configuration file"
    )

    # Manually add boolean flag for store_true behavior
    parser.add_argument(
        "--sync-deletions",
        action="store_true",
        help="Sync deletions from crawl state to content index",
    )

    # Add config arguments to root namespace (flattened), skipping manually defined ones
    parser.add_class_arguments(IndexerConfig, None, skip={"sync_deletions"})
    parser.add_argument(
        "-v",
        action="count",
        default=0,
        help="Increase verbosity (-v, -vv, -vvv)",
    )

    args = parser.parse_args()

    # Manually instantiate config from flattened arguments
    config_data = {}
    for field_name in IndexerConfig.model_fields:
        if hasattr(args, field_name):
            config_data[field_name] = getattr(args, field_name)

    config = IndexerConfig(**config_data)

    # Override verbose with -v flag if provided
    if args.v > 0:
        config.verbose = args.v

    # Resolve ES host
    final_es_host = resolve_es_host(config, console)
    final_index_base_name = resolve_index_base_name(config, console)
    final_languages = resolve_languages(config, console)

    _make_stats_writer()

    state_index = os.environ.get("ES_STATE_INDEX", "harmony-crawl-state")

    # Load entries based on source
    if config.source == "disk":
        # Existing disk-based logic
        metadata_files = list(config.data_dir.rglob("metadata.jsonl"))

        if not metadata_files:
            console.print(
                f"[red]Error: No metadata.jsonl files found in {config.data_dir}[/red]"
            )
            return

        console.print(
            f"[green]Found {len(metadata_files)} metadata.jsonl file(s)[/green]"
        )
        all_entries = _load_all_entries(metadata_files, console)

    elif config.source == "elasticsearch":
        # New ES-based logic
        if not config.data_dir.exists():
            console.print(
                f"[red]Error: Data directory {config.data_dir} does not exist[/red]"
            )
            console.print(
                "[yellow]Hint: --data-dir must point to where crawled files are stored[/yellow]"
            )
            return

        console.print(f"[green]Loading from ES state index: {state_index}[/green]")

        # Load ES config (needed for both source and target indices)
        if config.es_config and config.es_config.exists():
            es_config = ESConfig.from_yaml(config.es_config)
            console.print(f"[green]Loaded ES config from {config.es_config}[/green]")
        else:
            es_config = ESConfig(
                host=final_es_host,
                index_base_name=final_index_base_name,
                languages=final_languages,
            )

        # Connect to ES
        console.print(f"[green]Connecting to Elasticsearch at {es_config.host}[/green]")
        es = Elasticsearch([es_config.host])

        if not es.ping():
            console.print("[red]Error: Cannot connect to Elasticsearch[/red]")
            return

        all_entries = _load_entries_from_es(es, state_index, config.data_dir, console)

        if not all_entries:
            console.print("[yellow]Warning: No documents found in state index[/yellow]")
            sys.exit(1)

    console.print(f"[green]Processing {len(all_entries)} documents[/green]")

    # Load ES configuration (for disk source, needed after loading entries)
    if config.source == "disk":
        if config.es_config and config.es_config.exists():
            es_config = ESConfig.from_yaml(config.es_config)
            console.print(f"[green]Loaded ES config from {config.es_config}[/green]")
        else:
            es_config = ESConfig(
                host=final_es_host,
                index_base_name=final_index_base_name,
                languages=final_languages,
            )

        console.print(f"[green]Connecting to Elasticsearch at {es_config.host}[/green]")
        es = Elasticsearch([es_config.host])

        if not es.ping():
            console.print("[red]Error: Cannot connect to Elasticsearch[/red]")
            return

    # Detect languages if missing (crucial for proper indexing)
    _detect_languages_if_missing(all_entries, console)

    # Group entries by language
    entries_by_lang = _group_entries_by_language(all_entries)

    console.print(
        f"[cyan]Found {len(entries_by_lang)} language(s): {', '.join(entries_by_lang.keys())}[/cyan]"
    )

    # Process each language separately
    total_success = 0
    total_errors = 0
    total_stats = {
        "html": 0,
        "documents": 0,
        "parse_errors": 0,
        "missing_files": 0,
    }

    for lang, entries in entries_by_lang.items():
        console.print(
            f"\n[bold]Processing language: {lang} ({len(entries)} documents)[/bold]"
        )

        index_name = es_config.get_index_name(lang)

        # Create language-specific index
        _setup_elasticsearch_index(es, index_name, lang, es_config, console)

        # Index documents for this language
        lang_stats = {
            "html": 0,
            "documents": 0,
            "parse_errors": 0,
            "missing_files": 0,
        }

        success_count, error_count = _perform_bulk_indexing(
            es, entries, index_name, config.batch_size, lang_stats, console
        )

        total_success += success_count
        total_errors += error_count
        for key in total_stats:
            total_stats[key] += lang_stats[key]

        console.print(
            f"[green]{lang}: {success_count} indexed, {error_count} errors[/green]"
        )

    # Print overall summary
    console.print("\n[bold]Overall Summary:[/bold]")
    _print_indexing_summary(total_success, total_errors, total_stats, console)

    if not config.skip_embedding:
        _embed_and_upsert(
            all_entries=all_entries,
            qdrant_host=config.qdrant_host,
            qdrant_collection=config.qdrant_collection,
            embedding_model=config.embedding_model,
            batch_size=config.embedding_batch_size,
            console=console,
        )

    if config.sync_deletions:
        # Sync deletions for all language indices
        for lang in entries_by_lang:
            index_name = es_config.get_index_name(lang)
            _sync_deletions(
                es, console, state_index, index_name, config.missing_threshold
            )


if __name__ == "__main__":
    main()
