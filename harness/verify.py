"""Verification — no "done" without a real passing run.

A confident final sentence is not proof. The model doesn't get to just SAY a
change works; it has to run a real command (via the bash tool) and the
harness has to see a real passing exit code in the transcript before "done"
is accepted.

Language-agnostic on purpose: we read the command to run from AGENTS.md's
Testing section rather than hardcoding pytest/npm/go test/etc. The gate only
arms when the turn actually wrote a code file (by extension) — a plain
question never triggers it.
"""

import re
from pathlib import Path

CODE_EXTENSIONS = {".py", ".js", ".ts", ".go", ".rs", ".java", ".rb", ".c", ".cpp", ".sh"}


def get_test_command(workspace):
    """Read the command named in AGENTS.md's `## Testing` section. Returns
    None if there's no such section (verification simply doesn't arm)."""
    agents_md = workspace.root / "AGENTS.md"
    if not agents_md.exists():
        return None
    text = agents_md.read_text(encoding="utf-8")
    section = re.search(r"##\s*Testing\s*\n(.*?)(\n##|\Z)", text, re.DOTALL | re.IGNORECASE)
    if not section:
        return None
    command = re.search(r"`([^`]+)`", section.group(1))
    return command.group(1) if command else None


def is_code_file(path_str):
    """Whether a written path looks like a source file, by extension."""
    return Path(path_str).suffix.lower() in CODE_EXTENSIONS


def saw_passing_run(tool_result):
    """Heuristic: our sandbox's bash tool prefixes output with '[exit N]'.
    A real passing run looks like '[exit 0]'."""
    return "[exit 0]" in tool_result
