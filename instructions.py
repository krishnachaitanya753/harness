"""Instruction loading — folds layers into the agent's single system message.

Instructions are a *layer*, not a replacement: a built-in system prompt PLUS an
optional project AGENTS.md read from the workspace. Same convention as Codex and
Claude Code (which use AGENTS.md / CLAUDE.md). The file augments the built-in
prompt; it never overwrites it.
"""

from pathlib import Path


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
