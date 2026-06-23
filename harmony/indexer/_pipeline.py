from __future__ import annotations

import logging
import sys
import typing

from harmony.indexer._core import (
    EmbedContext,
    IndexByLanguageContext,
    RunIndexingContext,
    embed_and_upsert,
    index_by_language,
    sync_deletions,
)
from harmony.indexer._language import detect_languages_if_missing
from harmony.indexer._sources import group_entries_by_language, load_entries_from_source

logger = logging.getLogger(__name__)


async def run_indexing(ctx: RunIndexingContext, pool: typing.Any = None) -> None:
    if ctx.start_fresh and ctx.checkpoint_repo is not None:
        cleared = await ctx.checkpoint_repo.clear(ctx.config_name)
        logger.info(
            "cleared %d checkpoint entries for config '%s'", cleared, ctx.config_name
        )

    indexed_urls = (
        await ctx.checkpoint_repo.get_indexed_urls(ctx.config_name)
        if ctx.checkpoint_repo is not None
        else set()
    )
    logger.info("found %d already-indexed URLs in checkpoint", len(indexed_urls))

    result = await load_entries_from_source(
        ctx.config,
        ctx.final_es_host,
        ctx.final_index_base_name,
        ctx.final_languages,
        ctx.state_index,
    )
    if result is None:
        sys.exit(1)
    all_entries, es_service, es_config = result

    if indexed_urls:
        original_count = len(all_entries)
        all_entries = [e for e in all_entries if e.get("url") not in indexed_urls]
        skipped = original_count - len(all_entries)
        if skipped:
            logger.info("skipping %d already-indexed URLs", skipped)

    logger.info("processing %d documents", len(all_entries))
    detect_languages_if_missing(all_entries, ctx.stats_writer, len(all_entries))

    total_success, total_errors, total_stats = await index_by_language(
        IndexByLanguageContext(
            all_entries=all_entries,
            es_service=es_service,
            es_config=es_config,
            config=ctx.config,
            stats_writer=ctx.stats_writer,
            checkpoint_repo=ctx.checkpoint_repo,
            config_name=ctx.config_name,
            recreate=ctx.recreate,
        ),
        pool=pool,
    )

    logger.info(
        "indexing complete: %d success, %d errors; html=%d documents=%d parse_errors=%d missing_files=%d",
        total_success,
        total_errors,
        total_stats["html"],
        total_stats["documents"],
        total_stats["parse_errors"],
        total_stats["missing_files"],
    )

    if not ctx.config.skip_embedding:
        from harmony.clients import QdrantService  # noqa: PLC0415

        qdrant_service = QdrantService(
            host=ctx.config.qdrant_host,
            collection=ctx.config.qdrant_collection,
            vector_size=512,  # TODO: Hardcoded for now based on embedding model, could make dynamic
        )
        await embed_and_upsert(
            EmbedContext(
                all_entries=all_entries,
                qdrant_service=qdrant_service,
                embedding_model=ctx.config.embedding_model,
                batch_size=ctx.config.embedding_batch_size,
                stats_writer=ctx.stats_writer,
            )
        )

    if ctx.config.sync_deletions:
        entries_by_lang = group_entries_by_language(all_entries)
        for lang in entries_by_lang:
            index_name = es_config.get_index_name(lang)
            await sync_deletions(
                es_service,
                ctx.state_index,
                index_name,
                ctx.config.missing_threshold,
            )
