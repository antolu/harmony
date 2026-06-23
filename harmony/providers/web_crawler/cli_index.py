from __future__ import annotations

import asyncio
import logging
import os

from jsonargparse import ActionConfigFile, ArgumentParser

from harmony.db.connection import close_async_pool, get_async_pool
from harmony.db.repositories import IndexerCheckpointRepo
from harmony.indexer import (
    IndexerConfigCLI as IndexerConfig,
)
from harmony.indexer import (
    RunIndexingContext,
    make_stats_writer,
    resolve_configs,
    run_indexing,
)

logger = logging.getLogger(__name__)


def main() -> None:
    parser = ArgumentParser(
        prog="harmony-index",
        description="Index crawled data to Elasticsearch",
        default_config_files=["indexer_config.yaml"],
    )
    parser.add_argument(
        "--config", action=ActionConfigFile, help="Path to YAML configuration file"
    )

    parser.add_argument(
        "--sync-deletions",
        action="store_true",
        help="Sync deletions from crawl state to content index",
    )
    parser.add_argument(
        "--start-fresh",
        action="store_true",
        help="Clear existing checkpoint before indexing (re-index all documents)",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete and recreate ES indices before indexing (default: incremental upsert)",
    )

    parser.add_class_arguments(IndexerConfig, None, skip={"sync_deletions"})
    parser.add_argument(
        "--state_index",
        type=str,
        default=None,
        help="ES state index name (overrides ES_STATE_INDEX env var)",
    )
    parser.add_argument(
        "-v",
        action="count",
        default=0,
        help="Increase verbosity (-v, -vv, -vvv)",
    )

    args = parser.parse_args()

    config_data = {}
    for field_name in IndexerConfig.model_fields:
        if hasattr(args, field_name):
            config_data[field_name] = getattr(args, field_name)

    config = IndexerConfig(**config_data)

    if args.v > 0:
        config.verbose = args.v

    log_level = logging.DEBUG if config.verbose > 0 else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    async def async_main() -> None:
        pool = await get_async_pool() if os.environ.get("DATABASE_URL") else None

        final_es_host, final_index_base_name, final_languages = await resolve_configs(
            config, pool
        )
        stats_writer = make_stats_writer()
        state_index = args.state_index or os.environ.get(
            "ES_STATE_INDEX", "harmony-crawl-state"
        )

        config_name = getattr(args, "config_name", None) or os.environ.get(
            "HARMONY_CRAWL_JOB_ID", final_index_base_name
        )

        checkpoint_repo = IndexerCheckpointRepo(pool) if pool is not None else None

        try:
            await run_indexing(
                RunIndexingContext(
                    start_fresh=args.start_fresh,
                    recreate=args.recreate,
                    config=config,
                    checkpoint_repo=checkpoint_repo,
                    config_name=config_name,
                    final_es_host=final_es_host,
                    final_index_base_name=final_index_base_name,
                    final_languages=final_languages,
                    state_index=state_index,
                    stats_writer=stats_writer,
                ),
                pool=pool,
            )
        finally:
            if pool is not None:
                await close_async_pool()

    asyncio.run(async_main())


if __name__ == "__main__":
    main()
