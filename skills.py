"""Skills — operational memory via progressive disclosure.

A tool is a verb; a skill is a procedure — "how we do releases in this repo",
"how we sign off a task". A skill is just a directory with a SKILL.md: front
matter (name, description) up top, full instructions below.

The trick: we advertise only the name + one-line description in the system
prompt (cheap, paid every turn). The full body stays on disk until the model
itself decides — from that description — that a skill is relevant, then it
reads the file with the read_file tool it already has. The harness never
force-loads a skill; the model chooses, same as it chooses any other tool.
"""

import re
from pathlib import Path

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def _parse_frontmatter(text):
    """Pull simple 'key: value' pairs out of a --- ... --- header. No YAML lib
    needed for two flat fields."""
    match = _FRONTMATTER.match(text)
    if not match:
        return {}
    fields = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


def load_skills(workspace):
    """Scan skills/*/SKILL.md under the workspace root.

    Returns a list of {'name', 'description', 'path'} — path is relative, so
    the model can hand it straight to read_file.
    """
    skills_dir = workspace.root / "skills"
    if not skills_dir.is_dir():
        return []
    found = []
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        meta = _parse_frontmatter(skill_md.read_text(encoding="utf-8"))
        if "name" in meta and "description" in meta:
            rel_path = skill_md.relative_to(workspace.root)
            found.append({"name": meta["name"], "description": meta["description"], "path": str(rel_path)})
    return found


def render_skills(workspace):
    """The system-prompt block: skill ads + the instruction that tells the
    model WHEN to bother reading one. Without that instruction the ads are
    just inert text — this line is what turns them into a trigger."""
    skills = load_skills(workspace)
    if not skills:
        return ""

    lines = [f'- {s["name"]}: {s["description"]} (load with read_file: {s["path"]})' for s in skills]
    return (
        "You have skills available — stored procedures for how things are done "
        "in this project. Only their name and description are shown below; if "
        "one is relevant to what's being asked, read its file with read_file "
        "BEFORE acting, then follow its instructions.\n\n"
        "Available skills:\n" + "\n".join(lines)
    )
