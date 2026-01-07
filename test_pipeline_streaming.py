"""Test the pipeline streaming locally."""

from __future__ import annotations

import asyncio
import sys
import typing

sys.path.insert(0, "openwebui_pipelines")


async def test_pipeline() -> None:
    """Test the Harmony Agentic Search pipeline."""
    # Import after path is set
    from harmony_agentic_search import Pipeline  # noqa: PLC0415

    pipeline = Pipeline()
    print(f"Pipeline loaded: {pipeline.name}")
    print(f"Valves: {pipeline.valves}")

    # Test the pipe method
    user_message = "What is CERN?"
    model_id = "harmony_agentic_search"
    messages = [{"role": "user", "content": user_message}]
    body: dict[str, typing.Any] = {}

    print("\nStreaming response:")
    print("-" * 80)

    max_chunks = 10
    chunk_count = 0
    async for chunk in pipeline.pipe(user_message, model_id, messages, body):  # type: ignore[attr-defined]
        chunk_count += 1
        print(f"Chunk {chunk_count}: {chunk[:100]}...")
        if chunk_count > max_chunks:
            print(f"... (stopping after {max_chunks} chunks)")
            break

    print("-" * 80)
    print(f"Total chunks received: {chunk_count}")


if __name__ == "__main__":
    asyncio.run(test_pipeline())
