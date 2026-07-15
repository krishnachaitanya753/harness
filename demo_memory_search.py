"""Demo 3: episodic search — recall a fact from a DIFFERENT session, one this
agent never loaded as its active conversation. Proves search_memory scans
across all sessions on disk, not just the current one.

Run this only after demo_memory_part1.py has created sessions/demo.jsonl:
  uv run python demo_memory_search.py
"""

from agent import Agent, console_approver

# Deliberately a different (new) session — this agent has no memory of "demo".
agent = Agent(session="investigator", approver=console_approver)

print("You: Search memory for 'vault combination' and tell me what you find.")
print("Bot:", agent.run("Search memory for 'vault combination' and tell me what you find."))
