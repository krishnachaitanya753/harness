"""Demo: Ch 11 — subagents. Fan out two independent subtasks in parallel; each
runs in its own fresh, isolated agent (own messages[], own context). Neither
sees the other's reasoning; order of results is preserved.

Run (from the project root):  uv run python demos/demo_subagents.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))  # so `from harness.agent import ...` finds the root

from harness.agent import Agent

agent = Agent(workspace="scratch")

print("You: fan out two tasks — compute 12 squared, and name a primary color.")
reply = agent.run(
    "Use the fan_out tool with tasks: "
    '["Use the calculator tool to compute 12 squared and state the number.", '
    '"Name one primary color, one word only."]'
)
print("Bot:", reply)
