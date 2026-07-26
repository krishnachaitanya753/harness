"""Workspace — the directory an agent owns; every file path is confined to it.

.resolve() blocks two different things:
1. Escaping the root (../, absolute paths elsewhere) — the original boundary.
2. Secrets that live INSIDE the root — .env and friends are never outside the
   jail, so containment alone doesn't hide them. The rule from Ch 8: don't tell
   the model not to touch secrets, just don't give it secrets. This denylist is
   how that rule gets enforced in code, not in a prompt.

Every file tool (read_file, write_file, @-refs) routes through here, so the
fix protects all of them at once.
"""

import fnmatch
from pathlib import Path

# Filenames/patterns never readable through the workspace, no matter where
# they sit inside it. Matched against the final path component.
DENYLIST = [".env", "*.env", "*.pem", "*.key", "*credentials*", "*secret*"]


class Workspace:
    def __init__(self, root="."):
        # Absolute, normalized root. Everything must live inside this.
        self.root = Path(root).resolve()

    def resolve(self, relative_path):
        """Resolve a path inside the workspace, refusing anything that escapes
        it OR matches the secrets denylist.

        e.g. resolve('../secrets') escapes and is refused; resolve('.env') is
        inside the workspace but still refused, because it's a secret.
        """
        target = (self.root / relative_path).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError(f"Path {relative_path!r} escapes the workspace root {self.root}")
        if any(fnmatch.fnmatch(target.name.lower(), pat) for pat in DENYLIST):
            raise ValueError(f"Path {relative_path!r} matches the secrets denylist and is refused")
        return target
