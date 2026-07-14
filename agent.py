"""Agent — a conversation that remembers, now with a layered system prompt.

The Agent owns `self.messages` (conversation state) and a `Workspace` (the dir it
is confined to). Its system message is built from a layer: the built-in prompt
plus the project's AGENTS.md (see instructions.py).

Still deliberately minimal: no tools, no context management. Those arrive later as
*new methods* on this class, without changing how .send() is used.
"""

from client import LLMClient
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
        self.messages.append({"role": "user", "content": user_message})
        reply = self.client.chat(self.messages)
        self.messages.append({"role": "assistant", "content": reply})
        return reply


if __name__ == "__main__":
    # No identity passed in code — AGENTS.md provides it. Ask its name and it
    # should answer "Gemma", proving the instruction layer loaded.
    agent = Agent()

    print("You: What is your name?")
    print("Bot:", agent.send("What is your name? Answer in one short sentence."))
