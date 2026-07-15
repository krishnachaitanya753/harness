"""Agent — a conversation that remembers, follows instructions, reads files, and
now *acts* through tools.

Two entry points:
- send(): one plain chat turn (Ch 2-4).
- run():  the agentic tool loop (Ch 5). The model may call tools repeatedly until
          it gives a final answer, capped at MAX_STEPS so it can't spin forever.

The split to notice: the model only emits a JSON request for a tool; the harness
decides whether/how to run it (approval gate, workspace confinement) and feeds the
result back. The model never touches the machine directly.
"""

from client import LLMClient
from compaction import maybe_compact
from context import deliver
from instructions import build_system_prompt
from limits import TOKEN_BUDGET, clamp
from memory import load_session, save_session
from skills import render_skills
from tools import TOOLS, parse_tool_call, run_tool, tool_instructions
from workspace import Workspace

MAX_STEPS = 6  # cap the tool loop so a confused model can't loop forever


def console_approver(name, args):
    """Interactive approval gate: pause and ask the human at the terminal."""
    print(f"\n[approval needed] tool={name!r} args={args}")
    return input("approve? (y/n): ").strip().lower().startswith("y")


class Agent:
    def __init__(self, client=None, system_prompt="You are a helpful agent.",
                 workspace=".", approver=None, token_budget=TOKEN_BUDGET, session=None):
        self.client = client or LLMClient()
        self.workspace = Workspace(workspace)
        self.approver = approver  # callable(name, args) -> bool; None = deny everything
        self.token_budget = token_budget
        self.session = session  # session name; if set, conversation persists to disk

        # A resumed session's saved messages ARE the conversation state — load
        # verbatim instead of rebuilding, so a restarted process picks up
        # exactly where it left off.
        loaded = load_session(session) if session else None
        if loaded:
            self.messages = loaded
            return

        # No saved session (or none requested): build the system message fresh.
        # Built-in prompt + AGENTS.md + tool specs + skill ads.
        system = build_system_prompt(system_prompt, self.workspace.root)
        system += "\n\n" + tool_instructions()
        skills_block = render_skills(self.workspace)
        if skills_block:
            system += "\n\n" + skills_block
        self.messages = [{"role": "system", "content": system}]

    def _save(self):
        if self.session:
            save_session(self.session, self.messages)

    def send(self, user_message):
        """One plain turn (no tool loop)."""
        user_message = deliver(user_message, self.workspace)
        self.messages.append({"role": "user", "content": user_message})
        self._manage_context()
        reply = self.client.chat(self.messages)
        self.messages.append({"role": "assistant", "content": reply})
        self._save()
        return reply

    def _manage_context(self):
        """Compact the conversation if it has outgrown the budget. Prefers the
        model-reported token count (from the previous call) over the chars/4
        estimate, falling back to the estimate before the first call."""
        self.messages, compacted = maybe_compact(
            self.messages, self.client, self.token_budget, actual_tokens=self.client.last_usage,
        )
        if compacted:
            print("[context compacted]")

    def run(self, user_message):
        """Agentic loop: send -> if the model asks for a tool, run it and feed the
        result back -> repeat until a final (non-tool) answer or the step cap."""
        user_message = deliver(user_message, self.workspace)
        self.messages.append({"role": "user", "content": user_message})

        for _ in range(MAX_STEPS):
            self._manage_context()
            reply = self.client.chat(self.messages)
            self.messages.append({"role": "assistant", "content": reply})

            call = parse_tool_call(reply)
            if call is None:
                self._save()
                return reply  # no tool requested => this is the final answer

            name, args = call["tool"], call["args"]
            # Clamp so one giant tool output can't flood the window on its own.
            result = clamp(self._dispatch(name, args))
            # Hand the result back so the model can use it on the next turn.
            self.messages.append({"role": "user", "content": f"[tool result for {name}]: {result}"})

        self._save()
        return "Stopped: reached the step limit without a final answer."

    def _dispatch(self, name, args):
        """Run a requested tool, applying the approval gate for dangerous ones."""
        tool = TOOLS.get(name)
        if tool and tool.requires_approval:
            approved = self.approver(name, args) if self.approver else False
            if not approved:
                return f"Denied: {name} was not approved."
        return run_tool(name, args, self.workspace)


if __name__ == "__main__":
    # Demo runs in a scratch workspace so writes never touch the real repo.
    agent = Agent(workspace="scratch", approver=console_approver)

    print("=== calculator (runs free) ===")
    print("Bot:", agent.run("What is 12 * (3 + 4)? Use the calculator tool."))

    print("\n=== write_file (approval gate) ===")
    print("Bot:", agent.run("Write 'hello from the agent' to hello.txt using the write_file tool."))
