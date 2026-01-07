"""Quick test for LLM streaming."""

from __future__ import annotations

import asyncio

from harmony.api.services.llm import llm_service


async def test_stream() -> None:
    """Test streaming completion."""
    messages = [{"role": "user", "content": "Count from 1 to 5, one number per line."}]

    print("Testing LLM streaming...")
    print("Response: ", end="", flush=True)

    async for chunk in llm_service.stream_complete(messages):
        print(chunk, end="", flush=True)

    print("\n✓ Streaming test complete!")


if __name__ == "__main__":
    asyncio.run(test_stream())
