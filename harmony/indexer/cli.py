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


def main() -> None:  # noqa: PLR0915, PLR0912, PLR0914
    parser = argparse.ArgumentParser(description="Index crawled data to Elasticsearch")
    parser.add_argument(
        "--data-dir", required=True, help="Directory containing crawled data"
    )
    parser.add_argument(
        "--es-host", default="http://localhost:9200", help="Elasticsearch host"
    )
    parser.add_argument(
        "--index-name", default="harmony", help="Elasticsearch index name"
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

    # Find all metadata.jsonl files recursively
    metadata_files = list(data_dir.rglob("metadata.jsonl"))

    if not metadata_files:
        console.print(f"[red]Error: No metadata.jsonl files found in {data_dir}[/red]")
        return

    console.print(f"[green]Found {len(metadata_files)} metadata.jsonl file(s)[/green]")

    console.print(f"[green]Connecting to Elasticsearch at {args.es_host}[/green]")
    es = Elasticsearch([args.es_host])

    if not es.ping():
        console.print("[red]Error: Cannot connect to Elasticsearch[/red]")
        return

    console.print(f"[green]Creating index: {args.index_name}[/green]")

    index_settings = {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
        },
        "mappings": {
            "properties": {
                "url": {"type": "keyword"},
                "title": {
                    "type": "text",
                    "analyzer": "standard",
                    "fields": {
                        "en": {"type": "text", "analyzer": "english"},
                        "fr": {"type": "text", "analyzer": "french"},
                    },
                },
                "content": {
                    "type": "text",
                    "analyzer": "standard",
                    "fields": {
                        "en": {"type": "text", "analyzer": "english"},
                        "fr": {"type": "text", "analyzer": "french"},
                    },
                },
                "domain": {"type": "keyword"},
                "path": {"type": "keyword"},
                "depth": {"type": "integer"},
                "crawled_at": {"type": "date"},
                "file_path": {"type": "keyword"},
                "language": {"type": "keyword"},
            }
        },
    }

    if es.indices.exists(index=args.index_name):
        console.print(
            f"[yellow]Index {args.index_name} already exists, deleting...[/yellow]"
        )
        es.indices.delete(index=args.index_name)

    es.indices.create(index=args.index_name, body=index_settings)

    # Load all metadata entries from all files
    metadata_entries = []
    for metadata_file in metadata_files:
        console.print(f"[cyan]Reading {metadata_file}[/cyan]")
        with metadata_file.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    # Store the base directory for this metadata file
                    entry["_base_dir"] = metadata_file.parent
                    metadata_entries.append(entry)

    console.print(f"[green]Processing {len(metadata_entries)} documents[/green]")

    # Track statistics
    stats = {
        "html": 0,
        "documents": 0,
        "parse_errors": 0,
        "missing_files": 0,
    }

    def generate_docs() -> collections.abc.Generator[dict[str, typing.Any], None, None]:
        for entry in metadata_entries:
            base_dir = entry.pop("_base_dir")
            file_path = base_dir / entry["file_path"]

            if not file_path.exists():
                console.print(
                    f"[yellow]Warning: {file_path} not found, skipping[/yellow]"
                )
                stats["missing_files"] += 1
                continue

            doc_type = entry.get("type", "html")

            if doc_type == "document":
                title, content = process_document(entry, file_path)
                if title is None:
                    stats["parse_errors"] += 1
                    continue
                stats["documents"] += 1
            else:
                html = file_path.read_text(encoding="utf-8")
                title, content = extract_text_from_html(html)
                stats["html"] += 1

            doc = {
                "_index": args.index_name,
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

    def process_document(
        entry: dict[str, typing.Any], file_path: Path
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
            return title, content  # noqa: TRY300
        except CorruptDocumentError as e:
            console.print(f"[red]Parse error {file_path.name}: {e}[/red]")
            return None, None

    with Progress() as progress:
        task = progress.add_task(
            "[cyan]Indexing documents...", total=len(metadata_entries)
        )

        success_count = 0
        error_count = 0

        for ok, result in helpers.streaming_bulk(
            es,
            generate_docs(),
            chunk_size=args.batch_size,
            raise_on_error=False,
        ):
            if ok:
                success_count += 1
            else:
                error_count += 1
                console.print(f"[red]Error indexing: {result}[/red]")

            progress.update(task, advance=1)

    console.print("[green]Indexing complete![/green]")
    console.print(f"[green]  Success: {success_count}[/green]")
    if error_count > 0:
        console.print(f"[red]  Errors: {error_count}[/red]")
    console.print(
        f"[cyan]Stats: {stats['html']} HTML pages, {stats['documents']} documents, "
        f"{stats['parse_errors']} parse errors, {stats['missing_files']} missing files[/cyan]"
    )

    # Deletion sync (optional)
    if args.sync_deletions:
        console.print("\n[yellow]Syncing deletions from crawl state...[/yellow]")

        # Check if state index exists
        if not es.indices.exists(index=args.state_index):
            console.print(
                f"[red]Error: State index {args.state_index} does not exist[/red]"
            )
            return

        # Query for URLs with missing_count >= threshold
        query = {"query": {"range": {"missing_count": {"gte": args.missing_threshold}}}}

        try:
            response = es.search(
                index=args.state_index, body=query, size=10000, _source=False
            )
            urls_to_delete = [hit["_id"] for hit in response["hits"]["hits"]]

            if not urls_to_delete:
                console.print("[green]No URLs to delete[/green]")
            else:
                console.print(
                    f"[yellow]Deleting {len(urls_to_delete)} URLs...[/yellow]"
                )

                # Delete from content index
                delete_actions = [
                    {"_op_type": "delete", "_index": args.index_name, "_id": url}
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


if __name__ == "__main__":
    main()
