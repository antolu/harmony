from __future__ import annotations

import argparse
import json
from pathlib import Path

import bs4
from elasticsearch import Elasticsearch, helpers
from rich.console import Console
from rich.progress import Progress

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


def main() -> None:
    parser = argparse.ArgumentParser(description="Index crawled data to Elasticsearch")
    parser.add_argument("--data-dir", required=True, help="Directory containing crawled data")
    parser.add_argument("--es-host", default="http://localhost:9200", help="Elasticsearch host")
    parser.add_argument("--index-name", default="harmony", help="Elasticsearch index name")
    parser.add_argument("--batch-size", type=int, default=100, help="Bulk indexing batch size")

    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    metadata_file = data_dir / "metadata.jsonl"

    if not metadata_file.exists():
        console.print(f"[red]Error: {metadata_file} not found[/red]")
        return

    console.print(f"[green]Connecting to Elasticsearch at {args.es_host}[/green]")
    es = Elasticsearch([args.es_host])

    if not es.ping():
        console.print("[red]Error: Cannot connect to Elasticsearch[/red]")
        return

    console.print(f"[green]Creating index: {args.index_name}[/green]")

    index_settings = {
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
            }
        }
    }

    if es.indices.exists(index=args.index_name):
        console.print(f"[yellow]Index {args.index_name} already exists, deleting...[/yellow]")
        es.indices.delete(index=args.index_name)

    es.indices.create(index=args.index_name, body=index_settings)

    with metadata_file.open("r", encoding="utf-8") as f:
        metadata_entries = [json.loads(line) for line in f]

    console.print(f"[green]Processing {len(metadata_entries)} documents[/green]")

    def generate_docs():
        for entry in metadata_entries:
            html_file = data_dir / entry["file_path"]

            if not html_file.exists():
                console.print(f"[yellow]Warning: {html_file} not found, skipping[/yellow]")
                continue

            html = html_file.read_text(encoding="utf-8")
            title, content = extract_text_from_html(html)

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
                },
            }

            yield doc

    with Progress() as progress:
        task = progress.add_task("[cyan]Indexing documents...", total=len(metadata_entries))

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

    console.print(f"[green]Indexing complete![/green]")
    console.print(f"[green]  Success: {success_count}[/green]")
    if error_count > 0:
        console.print(f"[red]  Errors: {error_count}[/red]")


if __name__ == "__main__":
    main()
