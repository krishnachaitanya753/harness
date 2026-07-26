"""Demo 3: episodic search — recall a fact from a DIFFERENT session, one this
agent never loaded as its active conversation. Proves search_memory scans
across all sessions on disk, not just the current one.

Run this only after demo_memory_part1.py has created sessions/demo.jsonl
(from the project root):
  uv run python demos/demo_memory_search.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))  # so `from harness.agent import ...` finds the root

from harness.agent import Agent, console_approver

# Deliberately a different (new) session — this agent has no memory of "demo".
agent = Agent(session="investigator", approver=console_approver)

print("You: Search memory for 'vault combination' and tell me what you find.")
print("Bot:", agent.run("Search memory for 'vault combination' and tell me what you find."))
