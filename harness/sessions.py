"""Durable memory — sessions survive a process restart.

This is the "write" move from Ch 6 applied to the whole conversation: instead
of keeping messages only in RAM, we persist them to disk as JSONL (one JSON
object per line) after every turn, and reload them on startup. Kill the
process and start a new one with the same session name, and it picks up
exactly where it left off.

Episodic search is the companion piece: a plain keyword scan across ALL saved
sessions (not just the active one), so the agent can recall a fact from a
different past conversation. No embeddings — deliberately the simplest thing
that works.

Sessions live in a project-root sessions/ dir, separate from any agent's
`workspace` — this is harness bookkeeping, not agent-controlled file access,
so it isn't subject to the workspace jail.
"""

import json
from pathlib import Path

# .parent.parent because this module lives in harness/ — sessions/ belongs at
# the PROJECT root, not inside the package.
SESSIONS_DIR = Path(__file__).parent.parent / "sessions"


def save_session(name, messages):
    """Write the full message list to sessions/{name}.jsonl, one message per
    line. Overwrites each call — we always save the current full snapshot,
    not an incremental append, so a shrinking (compacted) history stays
    consistent on disk."""
    SESSIONS_DIR.mkdir(exist_ok=True)
    path = SESSIONS_DIR / f"{name}.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for message in messages:
            f.write(json.dumps(message) + "\n")


def list_sessions():
    """Every saved session as (name, message_count, modified_time), newest
    first. Used by the UI's /sessions command."""
    if not SESSIONS_DIR.is_dir():
        return []
    rows = []
    for path in SESSIONS_DIR.glob("*.jsonl"):
        count = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        rows.append((path.stem, count, path.stat().st_mtime))
    return sorted(rows, key=lambda r: r[2], reverse=True)


def load_session(name):
    """Return the saved message list for `name`, or None if it doesn't exist
    yet (first run of a new session name)."""
    path = SESSIONS_DIR / f"{name}.jsonl"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def search_sessions(query, limit=5):
    """Case-insensitive keyword scan across every saved session's messages.
    Returns short strings tagged with their source session, so a recalled
    fact is traceable to where it came from."""
    if not SESSIONS_DIR.is_dir():
        return []
    needle = query.lower()
    hits = []
    for path in sorted(SESSIONS_DIR.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            message = json.loads(line)
            content = message.get("content", "")
            if needle in content.lower():
                snippet = content if len(content) <= 200 else content[:200] + "..."
                hits.append(f'[{path.stem}/{message["role"]}] {snippet}')
                if len(hits) >= limit:
                    return hits
    return hits
