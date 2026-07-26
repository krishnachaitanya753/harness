"""Demo part 2 of 2: a FRESH process, same session name.

This Python interpreter never saw part 1. If the answer comes back correct,
the fact survived purely from sessions/demo.jsonl on disk, not from RAM.

Run this only after demo_memory_part1.py (from the project root):
  uv run python demos/demo_memory_part2.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))  # so `from harness.agent import ...` finds the root

from harness.agent import Agent

agent = Agent(session="demo")

print("You: What was the vault combination?")
print("Bot:", agent.send("What was the vault combination?"))
