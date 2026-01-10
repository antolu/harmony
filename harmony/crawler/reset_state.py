from __future__ import annotations

import sys

from elasticsearch import Elasticsearch


def main() -> None:
    """Reset the crawler state index by deleting it from Elasticsearch."""
    min_args = 2
    index_arg_position = 2

    if len(sys.argv) < min_args:
        print("Usage: harmony-reset-state <es_host> [index_name]")
        print("Example: harmony-reset-state http://localhost:9200")
        print("         harmony-reset-state http://localhost:9200 harmony-crawl-state")
        sys.exit(1)

    es_host = sys.argv[1]
    index_name = (
        sys.argv[index_arg_position]
        if len(sys.argv) > index_arg_position
        else "harmony-crawl-state"
    )

    print(f"Connecting to Elasticsearch at {es_host}...")
    client = Elasticsearch(es_host)

    try:
        if client.indices.exists(index=index_name):
            print(f"Deleting index '{index_name}'...")
            client.indices.delete(index=index_name)
            print(f"✓ Index '{index_name}' deleted successfully")
        else:
            print(f"Index '{index_name}' does not exist")
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
