"""Demo part 1 of 2: tell the agent a fact, then this process exits.

Run (from the project root):  uv run python demos/demo_memory_part1.py
Then:                          uv run python demos/demo_memory_part2.py   (a brand new process)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))  # so `from agent import ...` finds the root

from agent import Agent

agent = Agent(session="demo")

print("You: The vault combination is 7-19-42. Just confirm you've got it.")
print("Bot:", agent.send("The vault combination is 7-19-42. Just confirm you've got it."))
print("\n[process exiting now — sessions/demo.jsonl holds the conversation]")
