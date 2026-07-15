"""Demo part 2 of 2: a FRESH process, same session name.

This Python interpreter never saw part 1. If the answer comes back correct,
the fact survived purely from sessions/demo.jsonl on disk, not from RAM.

Run this only after demo_memory_part1.py:  uv run python demo_memory_part2.py
"""

from agent import Agent

agent = Agent(session="demo")

print("You: What was the vault combination?")
print("Bot:", agent.send("What was the vault combination?"))
