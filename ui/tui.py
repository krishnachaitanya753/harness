"""tui.py — the terminal UI. Two panes: chat (left) and a live trace (right).

The whole point, architecturally: the UI does NOT reimplement the agent. It
runs the exact same Agent, in a worker thread so the UI stays responsive, and
renders what the tracer records (reusing Ch 13's Tracer/sink mechanism
unchanged — a console sink became a RichLog sink here). Only this file
imports textual; every other module in the harness stays UI-agnostic.

The approval gate becomes a real modal (Allow/Deny buttons) instead of a
blocking console input() — the agent's worker thread pauses on a
threading.Event while the modal is shown and answered on the UI thread.

Scope note: we skip running this on an isolated git worktree (the tutorial's
version does, to protect the real checkout) — unnecessary complexity for a
single-branch learning repo. Everything still runs inside the `scratch`
workspace, same as every other demo.
"""

import threading

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, Label, RichLog

from harness.agent import Agent
from harness.tracer import Tracer


class ApprovalModal(ModalScreen[bool]):
    """Replaces the console y/n approval prompt with a real dialog."""

    def __init__(self, name, args):
        super().__init__()
        self.tool_name, self.tool_args = name, args

    def compose(self) -> ComposeResult:
        with Vertical(id="approval-box"):
            yield Label(f"Approve tool call?\n{self.tool_name}({self.tool_args})")
            with Horizontal():
                yield Button("Allow", id="allow", variant="success")
                yield Button("Deny", id="deny", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "allow")


class HarnessApp(App):
    CSS = """
    Horizontal { height: 1fr; }
    #chat-pane { width: 1fr; }
    #chat-log { border: solid $accent; height: 1fr; }
    #trace-log { width: 1fr; border: solid $accent; }
    #approval-box { width: 64; height: auto; border: thick $warning; padding: 1 2; }
    """

    def __init__(self):
        super().__init__()
        # Same Tracer as Ch 13; its sink just writes into the trace pane
        # instead of the console.
        self.tracer = Tracer(sinks=[self._trace_sink])
        self.agent = Agent(workspace="scratch", approver=self._tui_approver, tracer=self.tracer)

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="chat-pane"):
                yield RichLog(id="chat-log", wrap=True)
                yield Input(placeholder="Ask the agent...", id="chat-input")
            yield RichLog(id="trace-log", wrap=True)
        yield Footer()

    def _trace_sink(self, span):
        """Runs on the agent's worker thread — hop back to the UI thread
        (call_from_thread) before touching any widget."""
        line = f"{span.kind:9s} {span.name:14s} {span.duration_s:.2f}s  {span.attributes}"
        self.call_from_thread(self.query_one("#trace-log", RichLog).write, line)

    def _tui_approver(self, name, args):
        """Runs on the agent's worker thread. Blocks on a threading.Event
        while the modal is shown and answered on the UI thread — the same
        role console_approver played, just visual instead of blocking stdin."""
        result = {}
        done = threading.Event()

        def show_modal():
            def handle_result(approved):
                result["approved"] = approved
                done.set()
            self.push_screen(ApprovalModal(name, args), handle_result)

        self.call_from_thread(show_modal)
        done.wait()
        return result.get("approved", False)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value
        event.input.value = ""
        self.query_one("#chat-log", RichLog).write(f"You: {text}")
        self._run_agent(text)

    @work(thread=True)
    def _run_agent(self, text: str) -> None:
        """Runs agent.run() off the UI thread so approval modals and trace
        updates can render while the agent is still working."""
        reply = self.agent.run(text)
        self.call_from_thread(self.query_one("#chat-log", RichLog).write, f"Bot: {reply}")


if __name__ == "__main__":
    HarnessApp().run()
