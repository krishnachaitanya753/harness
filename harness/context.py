"""Context — everything that shapes what the model actually sees.

Four related concerns, small enough to live together:

1. Budgets & clamping   — how big is the conversation, and cap any one item.
2. Instructions         — the layered system prompt (built-in + AGENTS.md).
3. Delivery             — @file references pulled in ahead of the question.
4. Compaction           — summarize the middle when we cross the budget.

They're one file because they're one idea: managing the finite window. Split
them out if this grows past ~350 lines or the concerns start changing for
genuinely different reasons.
"""

import re
from pathlib import Path

# ---- 1. budgets & clamping -------------------------------------------------
# No LLM calls here — just arithmetic. Two cheap defenses against a flooded
# window: know roughly how big we are, and never let one item be huge.

TOKEN_BUDGET = 60_000        # when the conversation crosses this, compact it
MAX_ITEM_CHARS = 4_000       # cap for any one tool result / injected file
HEAD_KEEP = 2                # non-system messages protected at the start
TAIL_KEEP = 4                # messages protected at the end (the "now")


def estimate_tokens(messages):
    """Rough token count for a messages list: ~4 chars per token. Inexact on
    purpose — we only need "are we near the budget", not a perfect count."""
    return sum(len(m["content"]) for m in messages) // 4


def clamp(text, max_chars=MAX_ITEM_CHARS):
    """Cut oversized text, leaving a visible marker so the model knows it's partial."""
    if len(text) <= max_chars:
        return text
    cut = len(text) - max_chars
    return text[:max_chars] + f"\n...[clamped: {cut} chars omitted]"


# ---- 2. instructions -------------------------------------------------------
# Instructions are a *layer*, not a replacement: a built-in system prompt PLUS
# an optional project AGENTS.md. Same convention as Codex and Claude Code
# (AGENTS.md / CLAUDE.md). The file augments the built-in prompt, never
# overwrites it.


def load_agents_md(directory="."):
    """Return the text of AGENTS.md in `directory`, or '' if it doesn't exist."""
    path = Path(directory) / "AGENTS.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""  # absent file = no project instructions, not an error


def build_system_prompt(base_prompt, directory="."):
    """Fold the built-in prompt and the project's AGENTS.md into one string.

    The built-in prompt comes first (the harness's own voice), then the project
    rules layered underneath.
    """
    project = load_agents_md(directory)
    if project:
        return f"{base_prompt}\n\n{project}"
    return base_prompt


# ---- 3. delivery -----------------------------------------------------------
# The agent only ever sees the text we hand it. An @path token means "read that
# file and put its contents in front of my question". Every ref goes through
# Workspace.resolve(), so @../../.env is refused — the harness cannot deliver
# files outside the project or anything on the secrets denylist.

# An @ref is @ followed by a path-like token (letters, digits, / \ . _ -).
_REF = re.compile(r"@([\w./\\-]+)")


def deliver(message, workspace):
    """Expand @path references in `message` into injected file contents.

    Returns the message with each referenced file's contents prepended as a
    labelled block. Unreadable/blocked refs become a visible note instead of
    crashing, so the model still knows the reference was attempted.
    """
    refs = _REF.findall(message)
    if not refs:
        return message  # nothing to deliver; hand the message through unchanged

    blocks = []
    for ref in refs:
        try:
            path = workspace.resolve(ref)  # confinement happens here
            text = clamp(path.read_text(encoding="utf-8"))  # a giant file can't flood the window
            blocks.append(f"[Contents of {ref}]:\n{text}")
        except (OSError, ValueError) as e:
            blocks.append(f"[Could not read {ref}: {e}]")

    return "\n\n".join(blocks) + "\n\n" + message


# ---- 4. compaction ---------------------------------------------------------
# When we cross the budget, summarize the MIDDLE and keep head and tail
# verbatim. Why those: models recall the start and end of a long context most
# reliably ("lost in the middle"), the head holds the system prompt + goal, and
# the tail holds what we're doing right now.
#
# The summarizer is itself an LLM call — the harness uses the model to manage
# the model's own context. Compaction is lossy and permanent: if the summary
# drops a fact, the agent no longer knows it ever knew it.

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
