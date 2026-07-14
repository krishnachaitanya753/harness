"""Workspace — the directory an agent owns; every file path is confined to it.

Today this is a boundary object with no teeth: nothing reads or writes through it
yet. The write/edit tools of later chapters will route their paths through
.resolve() so the agent physically cannot touch anything outside its root. We
plant the boundary now, before the agent ever gets file access.
"""

from pathlib import Path


class Workspace:
    def __init__(self, root="."):
        # Absolute, normalized root. Everything must live inside this.
        self.root = Path(root).resolve()

    def resolve(self, relative_path):
        """Resolve a path inside the workspace, refusing anything that escapes it.

        e.g. resolve('../secrets') or an absolute path pointing elsewhere raises,
        so a later file tool can't be tricked into leaving the workspace.
        """
        target = (self.root / relative_path).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError(f"Path {relative_path!r} escapes the workspace root {self.root}")
        return target
