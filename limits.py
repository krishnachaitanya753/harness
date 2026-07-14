"""Limits — the budget arithmetic for context management. No LLM calls here.

Two cheap defenses against a flooded context window:
- estimate_tokens: know roughly how big the conversation is (chars/4 heuristic —
  inexact on purpose; we only need "are we near the budget", not a perfect count).
- clamp: no single item (tool result, @file contents) gets to be huge, no matter
  what the file or tool produced.
"""

TOKEN_BUDGET = 60_000        # when the conversation crosses this, compact it
MAX_ITEM_CHARS = 4_000       # cap for any one tool result / injected file
HEAD_KEEP = 2                # non-system messages protected at the start
TAIL_KEEP = 4                # messages protected at the end (the "now")


def estimate_tokens(messages):
    """Rough token count for a messages list: ~4 chars per token."""
    return sum(len(m["content"]) for m in messages) // 4


def clamp(text, max_chars=MAX_ITEM_CHARS):
    """Cut oversized text, leaving a visible marker so the model knows it's partial."""
    if len(text) <= max_chars:
        return text
    cut = len(text) - max_chars
    return text[:max_chars] + f"\n...[clamped: {cut} chars omitted]"
