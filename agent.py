"""Agent — a conversation that remembers, now with a layered system prompt.

The Agent owns `self.messages` (conversation state) and a `Workspace` (the dir it
is confined to). Its system message is built from a layer: the built-in prompt
plus the project's AGENTS.md (see instructions.py).

Still deliberately minimal: no tools, no context management. Those arrive later as
*new methods* on this class, without changing how .send() is used.
"""

from client import LLMClient
from context import deliver
from instructions import build_system_prompt
from workspace import Workspace


class Agent:
    def __init__(self, client=None, system_prompt="You are a helpful agent.", workspace="."):
        self.client = client or LLMClient()
        self.workspace = Workspace(workspace)
        # Instructions are a layer: built-in prompt + optional AGENTS.md from the
        # workspace. Set once here, prepended on every turn as the system message.
        system = build_system_prompt(system_prompt, self.workspace.root)
        self.messages = [{"role": "system", "content": system}]

    def send(self, user_message):
        """Run one turn: record the user message, get a reply, record it, return it."""
        # Context delivery: expand any @file references into their contents first.
        user_message = deliver(user_message, self.workspace)
        self.messages.append({"role": "user", "content": user_message})
        reply = self.client.chat(self.messages)
        self.messages.append({"role": "assistant", "content": reply})
        return reply


if __name__ == "__main__":
    agent = Agent()

    # Context delivery: @facts.txt is read off disk and injected before the
    # question, so the model can answer from a file it was never told directly.
    q = "@facts.txt Based only on the file, who is Raveena? Answer in one short sentence."
    print("You:", q)
    print("Bot:", agent.send(q))
