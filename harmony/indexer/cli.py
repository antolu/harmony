from __future__ import annotations

import argparse
import collections.abc
import json
import typing
from pathlib import Path

import bs4
from elasticsearch import Elasticsearch, helpers
from rich.console import Console
from rich.progress import Progress

from harmony.config.elasticsearch import ESConfig
from harmony.indexer.parsers import CorruptDocumentError, default_registry

console = Console()


def extract_text_from_html(html: str) -> tuple[str, str]:
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
        response = es.search(index=state_index, body=query, size=10000, _source=False)
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
            html = file_path.read_text(encoding="utf-8")
            title, content = extract_text_from_html(html)
            stats["html"] += 1

        doc = {
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

        yield doc


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Index crawled data to Elasticsearch")
    parser.add_argument(
        "--data-dir", required=True, help="Directory containing crawled data"
    )
    parser.add_argument(
        "--es-config", type=Path, help="Path to Elasticsearch YAML config file"
    )
    parser.add_argument(
        "--es-host", default="http://localhost:9200", help="Elasticsearch host"
    )
    parser.add_argument(
        "--index-base-name",
        default="harmony",
        help="Base name for indices (e.g., harmony-en, harmony-fr)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=100, help="Bulk indexing batch size"
    )
    parser.add_argument(
        "--sync-deletions",
        action="store_true",
        help="Sync deletions from crawl state to content index",
    )
    parser.add_argument(
        "--state-index",
        default="harmony-crawl-state",
        help="Crawl state index name (for deletion sync)",
    )
    parser.add_argument(
        "--missing-threshold",
        type=int,
        default=3,
        help="Number of crawls before deletion (for deletion sync)",
    )

    args = parser.parse_args()

    data_dir = Path(args.data_dir)

    metadata_files = list(data_dir.rglob("metadata.jsonl"))

    if not metadata_files:
        console.print(f"[red]Error: No metadata.jsonl files found in {data_dir}[/red]")
        return

    console.print(f"[green]Found {len(metadata_files)} metadata.jsonl file(s)[/green]")

    # Load ES configuration
    if args.es_config and args.es_config.exists():
        es_config = ESConfig.from_yaml(args.es_config)
        console.print(f"[green]Loaded ES config from {args.es_config}[/green]")
    else:
        es_config = ESConfig(host=args.es_host, index_base_name=args.index_base_name)

    console.print(f"[green]Connecting to Elasticsearch at {es_config.host}[/green]")
    es = Elasticsearch([es_config.host])

    if not es.ping():
        console.print("[red]Error: Cannot connect to Elasticsearch[/red]")
        return

    all_entries = _load_all_entries(metadata_files, console)

    console.print(f"[green]Processing {len(all_entries)} documents[/green]")

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
            es, entries, index_name, args.batch_size, lang_stats, console
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

    if args.sync_deletions:
        # Sync deletions for all language indices
        for lang in entries_by_lang:
            index_name = es_config.get_index_name(lang)
            _sync_deletions(
                es, console, args.state_index, index_name, args.missing_threshold
            )


if __name__ == "__main__":
    main()
