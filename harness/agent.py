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

import time

from harness.context import (
    TOKEN_BUDGET,
    build_system_prompt,
    clamp,
    deliver,
    maybe_compact,
)
from harness.sessions import load_session, save_session
from harness.skills import render_skills
from harness.tools import TOOLS, parse_tool_call, run_tool, tool_instructions
from harness.verify import get_test_command, is_code_file, saw_passing_run
from harness.workspace import Workspace
from model.client import LLMClient
from model.pricing import estimate_cost

MAX_STEPS = 6         # cap the tool loop so a confused model can't loop forever
VERIFY_MAX_STEPS = 3  # extra budget for the "prove it passed" round (Ch 12)


def console_approver(name, args):
    """Interactive approval gate: pause and ask the human at the terminal."""
    print(f"\n[approval needed] tool={name!r} args={args}")
    return input("approve? (y/n): ").strip().lower().startswith("y")


class Agent:
    def __init__(self, client=None, system_prompt="You are a helpful agent.",
                 workspace=".", approver=None, token_budget=TOKEN_BUDGET, session=None,
                 tracer=None, on_token=None):
        self.client = client or LLMClient()
        self.workspace = Workspace(workspace)
        self.approver = approver  # callable(name, args) -> bool; None = deny everything
        self.token_budget = token_budget
        self.session = session  # session name; if set, conversation persists to disk
        self.tracer = tracer  # Tracer or None; records a span per model/tool call (Ch 13)
        # on_token: fn(delta) — set by a UI that wants to render tokens live.
        # Left None everywhere else (subagents, orchestrator steps, compaction),
        # which is why those paths needed no changes when streaming landed.
        self.on_token = on_token
        self._wrote_code_file = False  # tracks whether this run() touched a code file (Ch 12)

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

    def _call_model(self):
        """Call the model, recording a traced span if a tracer is attached.
        Every call site (send, the tool loop, verification) routes through
        here so tracing doesn't have to be duplicated at each one."""
        if not self.tracer:
            return self.client.chat(self.messages, on_token=self.on_token)

        # Time to first token: the number that actually tracks how fast this
        # *feels*, as opposed to total duration. Only meaningful when streaming.
        first_token_at = []

        def timed_on_token(delta):
            if not first_token_at:
                first_token_at.append(time.monotonic())
            self.on_token(delta)

        # Span name is the operation; provider/model go in attributes and are
        # read AFTER the call, so a fallback shows the model that actually
        # answered rather than the one we intended to use. A trace that names
        # the default model would quietly lie (and misprice) on every fallback.
        with self.tracer.timed("llm_call", "chat") as attrs:
            started = time.monotonic()
            reply = self.client.chat(
                self.messages, on_token=timed_on_token if self.on_token else None
            )
            attrs["provider"] = self.client.last_provider
            attrs["model"] = self.client.last_model
            attrs["tokens"] = self.client.last_usage
            attrs["cost"] = round(estimate_cost(self.client.last_model, self.client.last_usage or 0), 4)
            if first_token_at:
                attrs["ttft"] = f"{first_token_at[0] - started:.2f}s"
        return reply

    def send(self, user_message):
        """One plain turn (no tool loop)."""
        user_message = deliver(user_message, self.workspace)
        self.messages.append({"role": "user", "content": user_message})
        self._manage_context()
        reply = self._call_model()
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
        self._wrote_code_file = False

        for _ in range(MAX_STEPS):
            self._manage_context()
            reply = self._call_model()
            self.messages.append({"role": "assistant", "content": reply})

            call = parse_tool_call(reply)
            if call is None:
                return self._verify_if_needed(reply)  # no tool requested => proposed final answer

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

        if self.tracer:
            with self.tracer.timed("tool_call", name) as attrs:
                attrs["args"] = args
                result = run_tool(name, args, self.workspace)
                attrs["result"] = result if len(str(result)) <= 200 else str(result)[:200] + "..."
        else:
            result = run_tool(name, args, self.workspace)

        if name == "write_file" and is_code_file(args.get("path", "")):
            self._wrote_code_file = True  # arms the verification gate (Ch 12)
        return result

    def _verify_if_needed(self, reply):
        """Ch 12: a confident sentence is not proof. If this turn wrote a code
        file and AGENTS.md names a test command, don't accept "done" until we
        see a REAL passing run of it in the transcript — force the model to
        actually run it via bash rather than just claiming success."""
        test_command = get_test_command(self.workspace) if self._wrote_code_file else None
        if not test_command:
            self._save()
            return reply  # gate doesn't arm: no code touched, or no test command configured

        self.messages.append({
            "role": "user",
            "content": f"Before finishing: run `{test_command}` via the bash tool and show "
                       "a real passing result. Don't just say it passes.",
        })
        for _ in range(VERIFY_MAX_STEPS):
            self._manage_context()
            reply = self._call_model()
            self.messages.append({"role": "assistant", "content": reply})

            call = parse_tool_call(reply)
            if call is None:
                self.messages.append({"role": "user", "content": "That's not a real run. Use the bash tool."})
                continue

            name, args = call["tool"], call["args"]
            result = clamp(self._dispatch(name, args))
            self.messages.append({"role": "user", "content": f"[tool result for {name}]: {result}"})
            if name == "bash" and saw_passing_run(result):
                final = self._call_model()
                self.messages.append({"role": "assistant", "content": final})
                self._save()
                return final

        self._save()
        return f"Verification failed: no passing run of `{test_command}` observed."


if __name__ == "__main__":
    # Demo runs in a scratch workspace so writes never touch the real repo.
    agent = Agent(workspace="scratch", approver=console_approver)

    print("=== calculator (runs free) ===")
    print("Bot:", agent.run("What is 12 * (3 + 4)? Use the calculator tool."))

    print("\n=== write_file (approval gate) ===")
    print("Bot:", agent.run("Write 'hello from the agent' to hello.txt using the write_file tool."))
