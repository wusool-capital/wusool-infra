"""
app/modules/meetings/domain/chunking.py

Token-budget-aware text chunker for feeding long transcripts to an LLM.

Uses a simple character-count heuristic (~4 characters per token)
rather than a real tokenizer (tiktoken, etc.) deliberately: this
project switches between OpenAI (dev) and Bedrock/Claude (prod), which
use different tokenizers, so no single exact token count would be
correct for both anyway. The heuristic is conservative enough (see
_CHARS_PER_TOKEN) to stay safely under real context windows.
"""

from __future__ import annotations

__all__ = ["chunk_text", "estimate_tokens"]

_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Rough token-count estimate. Deliberately approximate — see module docstring."""
    return max(1, len(text) // _CHARS_PER_TOKEN)


def chunk_text(text: str, *, max_tokens_per_chunk: int = 3000) -> list[str]:
    """Split *text* into chunks that each fit within *max_tokens_per_chunk*.

    Splits on paragraph boundaries where possible so a chunk doesn't cut
    a sentence in half; falls back to a hard character split only if a
    single paragraph alone exceeds the budget.
    """
    max_chars = max_tokens_per_chunk * _CHARS_PER_TOKEN
    if len(text) <= max_chars:
        return [text] if text else []

    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        if len(paragraph) <= max_chars:
            current = paragraph
        else:
            # A single paragraph is itself too large — hard-split it.
            for start in range(0, len(paragraph), max_chars):
                chunks.append(paragraph[start : start + max_chars])

    if current:
        chunks.append(current)

    return chunks
