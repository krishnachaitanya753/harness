"""Demo: Ch 12 — verification. Ask the agent to write a Python file. Because
it's a .py file and AGENTS.md names a testing command, the harness should NOT
accept "done" until it sees the model actually run
`python -m py_compile <file>` via bash and get a real passing exit code.

Run (from the project root):  uv run python demos/demo_verify.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))  # so `from harness.agent import ...` finds the root

from harness.agent import Agent, console_approver

agent = Agent(workspace="scratch", approver=console_approver)

print("You: write a small valid Python script to output.py using write_file.")
reply = agent.run(
    "Use write_file to create output.py containing a valid Python script that "
    "prints 'hello from output.py'. Then say you're done."
)
print("\nBot:", reply)
