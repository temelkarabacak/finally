"""Manual live smoke check: confirms response_format survives the wire to
gpt-oss-120b on Cerebras via OpenRouter.

Not part of the automated test suite and not a CI step -- a plain developer
script. LLM_MOCK by construction never exercises the real litellm +
response_format path (03-AI-SPEC.md Section 3, Pitfalls 1-2), so this
script is the only thing that can detect the OpenRouter adapter dropping
the schema before it reaches the provider.

Requires network access and OPENROUTER_API_KEY set in the environment (or
the project-root .env). Costs a fraction of a cent per run.

Run with:  uv run --directory backend python scripts/llm_smoke_check.py
"""

from __future__ import annotations

import asyncio
import os
import sys

from app.llm.client import get_chat_response

PROMPTS = [
    "Analyze my portfolio.",
    "Buy 10 shares of AAPL.",
    "What should I buy?",
]

SYSTEM_MESSAGE = {
    "role": "system",
    "content": (
        "You are FinAlly, an AI trading assistant. Always respond with valid structured JSON."
    ),
}


async def _run_prompt(prompt: str) -> None:
    """Send one prompt and report whether structured-output parsing succeeded."""
    messages = [SYSTEM_MESSAGE, {"role": "user", "content": prompt}]
    result = await get_chat_response(messages)

    if result is None:
        print(f"[FAIL] {prompt!r}: get_chat_response returned None (timeout or malformed output)")
        return

    print(f"[OK]   {prompt!r}")
    print(f"       message: {result.message!r}")
    print(f"       trades={len(result.trades)} watchlist_changes={len(result.watchlist_changes)}")


async def main() -> None:
    for prompt in PROMPTS:
        await _run_prompt(prompt)


if __name__ == "__main__":
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("OPENROUTER_API_KEY is not set -- this script requires a real API key.")
        sys.exit(1)

    asyncio.run(main())
