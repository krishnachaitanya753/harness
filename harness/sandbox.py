"""Sandbox — where untrusted (model-requested) shell commands actually run.

No Docker on this machine, so this is the scrubbed-subprocess fallback only:
a confined working directory, a minimal environment (no API keys or other
host secrets forwarded), and a timeout so a runaway command can't hang the
agent forever.

Honest limitation: without a container/VM, this does NOT give network or
filesystem isolation — an approved command could still reach the network or
read paths outside the workspace directly. The approval gate (Ch 5) is the
real backstop here, same as it is for write_file. If Docker is ever installed
again, this module is where a container-backed run_shell would replace this
one, without touching tools.py or agent.py.
"""

import subprocess

TIMEOUT_SECONDS = 15

# Only what a basic command needs to find its binaries. Nothing else — no
# GOOGLE_API_KEY, no GROQ_API_KEY, no random host env vars leak in.
_SAFE_ENV_KEYS = ["PATH", "SYSTEMROOT", "COMSPEC"]


def run_shell(command, workspace):
    """Run a shell command confined to the workspace directory with a scrubbed
    environment. Returns combined stdout+stderr, always as a string (never
    raises — a failing command is a normal result, not a harness error)."""
    import os

    env = {k: os.environ[k] for k in _SAFE_ENV_KEYS if k in os.environ}
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=workspace.root,
            env=env,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
        output = (result.stdout + result.stderr).strip()
        return f"[exit {result.returncode}]\n{output}" if output else f"[exit {result.returncode}]"
    except subprocess.TimeoutExpired:
        return f"[timed out after {TIMEOUT_SECONDS}s]"
