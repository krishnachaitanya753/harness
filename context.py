"""Context delivery — pull @-referenced files into the model's view.

The agent only ever sees the text we hand it. To let the user point at a file, we
pick a marker symbol (@): any @path token in a message means "read that file and
put its contents in front of my question". Before each call the harness scans for
@refs, reads them (confined to the workspace), and injects the contents.

Every ref goes through Workspace.resolve(), so a reference like @../../.env is
refused — the harness cannot deliver files outside the project.

Raw for now: it reads the whole file. Capping big files so they don't flood the
context window is a later chapter.
"""

import re

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
            text = path.read_text(encoding="utf-8")
            blocks.append(f"[Contents of {ref}]:\n{text}")
        except (OSError, ValueError) as e:
            blocks.append(f"[Could not read {ref}: {e}]")

    return "\n\n".join(blocks) + "\n\n" + message
