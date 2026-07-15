"""Demo part 1 of 2: tell the agent a fact, then this process exits.

Run:  uv run python demo_memory_part1.py
Then: uv run python demo_memory_part2.py   (a brand new process)
"""

from agent import Agent

agent = Agent(session="demo")

print("You: The vault combination is 7-19-42. Just confirm you've got it.")
print("Bot:", agent.send("The vault combination is 7-19-42. Just confirm you've got it."))
print("\n[process exiting now — sessions/demo.jsonl holds the conversation]")
