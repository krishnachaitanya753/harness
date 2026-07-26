"""Demo: progressive disclosure — the model decides whether to load a skill.

We never inject the sign-off skill's body anywhere. Its system-prompt footprint
is one line: name + description. If the reply contains "NIMBUS-7", that word
exists nowhere except skills/sign-off/SKILL.md, which proves the model chose to
call read_file on it — the description alone was enough to trigger the read.

Run (from the project root):  uv run python demos/demo_skills.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))  # so `from agent import ...` finds the root

from agent import Agent, console_approver

agent = Agent(workspace=".", approver=console_approver)

print("You: Please sign off on this task.")
print("Bot:", agent.run("Please sign off on this task."))

print("\nYou: What's 6 * 7? No need to sign off, just answer.")
print("Bot:", agent.run("What's 6 * 7? No need to sign off, just answer."))
