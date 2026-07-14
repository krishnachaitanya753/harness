"""Demo: compaction under a deliberately tiny budget.

We plant a code name in the FIRST turn (the protected head), bury it under filler
chatter until the conversation blows past the budget, and then ask for it. The
middle gets summarized away; the head survives verbatim — so it should remember.

Run:  uv run python demo_compaction.py
"""

from agent import Agent
from limits import estimate_tokens

agent = Agent(token_budget=800)  # tiny on purpose; real default is 60k

print("You: The secret code name is Crime Master Gogo. Remember it.")
agent.send("The secret code name is Crime Master Gogo. Remember it. Just say OK.")

for i in range(1, 5):
    print(f"\n[filler turn {i}]  (tokens so far: ~{estimate_tokens(agent.messages)})")
    agent.send(f"Filler chatter #{i}: give me a one-line fun fact about the number {i}.")

print(f"\n[before the question: {len(agent.messages)} messages, ~{estimate_tokens(agent.messages)} tokens]")
print("\nYou: What is the secret code name?")
print("Bot:", agent.send("What is the secret code name? Answer in one short sentence."))

print(f"\n[after: {len(agent.messages)} messages — look for the '[context compacted]' line above]")
