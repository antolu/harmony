from __future__ import annotations

import argparse
import os
import sys

from elasticsearch import Elasticsearch


class AclBackfillJob:
    def __init__(self, es_host: str, index_base: str, languages: list[str]) -> None:
        self._es = Elasticsearch([es_host])
        self._index_base = index_base
        self._languages = languages

    def _target_indices(self) -> list[str]:
        return [f"{self._index_base}-crawl-state"] + [
            f"{self._index_base}-{lang}" for lang in self._languages
        ]

    def run(
        self, source_pattern: str, allowed_roles: list[str], *, dry_run: bool = False
    ) -> int:
        query = {"query": {"wildcard": {"url": {"value": source_pattern}}}}
        indices = self._target_indices()

        if dry_run:
            resp = self._es.count(index=",".join(indices), body=query)
            return resp["count"]

        script = {
            "source": "ctx._source.acl = params.acl",
            "lang": "painless",
            "params": {
                "acl": {
                    "allowed_roles": allowed_roles,
                    "policy_version": "v1",
                }
            },
        }

        total_updated = 0
        for index in indices:
            resp = self._es.update_by_query(
                index=index,
                body={"query": query["query"], "script": script},
            )
            total_updated += resp.get("updated", 0)

        return total_updated


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="harmony-acl-backfill",
        description="Backfill ACL metadata on existing indexed documents",
    )
    parser.add_argument(
        "--source", required=True, help="fnmatch glob matched against document URL"
    )
    parser.add_argument(
        "--allowed-roles", required=True, help="Comma-separated list of roles"
    )
    parser.add_argument(
        "--es-host",
        default=os.environ.get("ES_HOST", "http://localhost:9200"),
    )
    parser.add_argument(
        "--index-base",
        default=os.environ.get("ES_INDEX_BASE_NAME", "harmony"),
    )
    parser.add_argument(
        "--languages",
        default="en,fr,de,es,it,pt,nl,ru,ar,zh,ja,ko",
    )
    parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    allowed_roles = [r.strip() for r in args.allowed_roles.split(",") if r.strip()]
    languages = [lang.strip() for lang in args.languages.split(",") if lang.strip()]

    try:
        job = AclBackfillJob(args.es_host, args.index_base, languages)
        count = job.run(args.source, allowed_roles, dry_run=args.dry_run)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if count == 0:
        print("No documents matched")
    elif args.dry_run:
        print(f"Dry run: {count} documents matched")
    else:
        print(f"Updated {count} documents")

    sys.exit(0)


if __name__ == "__main__":
    main()
