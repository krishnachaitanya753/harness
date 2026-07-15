"""Compaction — the "compress" move of context management.

When the conversation crosses the token budget, summarize the MIDDLE and keep the
head and tail verbatim. Why those: models recall the start and end of a long
context most reliably ("lost in the middle"), the head holds the system prompt +
goal, and the tail holds what we're doing right now.

The summarizer is itself an LLM call — the harness uses the model to manage the
model's own context. Note: compaction is lossy and permanent; if the summary
drops a fact, the agent no longer knows it ever knew it.
"""

from limits import HEAD_KEEP, TAIL_KEEP, TOKEN_BUDGET, estimate_tokens

SUMMARY_PROMPT = (
    "Summarize this conversation excerpt into a compact note. Preserve: the goal, "
    "any decisions made, and every concrete fact (names, numbers, file paths, "
    "results). Drop pleasantries and repetition. Plain prose, no preamble."
)


def maybe_compact(messages, client, budget=TOKEN_BUDGET, actual_tokens=None):
    """Return (messages, did_compact). Compacts only when over budget.

    `actual_tokens`: the model-reported count from the last response (see
    LLMClient.last_usage), preferred over the chars/4 estimate when we have
    one. It lags by one turn (it's the count from BEFORE the message we're
    about to send), which is fine — we only need "are we near the budget",
    not a perfect live count.

    Shape: [system] + head + [summary note] + tail — the system message is never
    touched, and the middle collapses into one message.
    """
    token_count = actual_tokens if actual_tokens is not None else estimate_tokens(messages)
    if token_count <= budget:
        return messages, False

    system, rest = messages[:1], messages[1:]
    if len(rest) <= HEAD_KEEP + TAIL_KEEP:
        return messages, False  # nothing in the middle to compress

    head = rest[:HEAD_KEEP]
    middle = rest[HEAD_KEEP:-TAIL_KEEP]
    tail = rest[-TAIL_KEEP:]

    transcript = "\n".join(f'{m["role"]}: {m["content"]}' for m in middle)
    summary = client.chat([
        {"role": "system", "content": SUMMARY_PROMPT},
        {"role": "user", "content": transcript},
    ])

    note = {
        "role": "user",
        "content": f"[context compacted — summary of {len(middle)} earlier messages]:\n{summary}",
    }
    return system + head + [note] + tail, True
