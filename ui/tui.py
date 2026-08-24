"""tui.py — the terminal UI: a real chat client for the harness.

The architectural point stays the same as when this file was 100 lines: the UI
does NOT reimplement the agent. It runs the exact same Agent in a worker thread
and renders what the tracer and the token stream give it. Only this file imports
textual; every other module stays UI-agnostic.

What makes it feel like a chat app rather than a REPL:

- a scrolling transcript of message widgets, not a log of strings
- replies stream token-by-token, then re-render as markdown (code blocks and
  all) once complete
- tool calls appear as their own cards, built from the SAME tracer spans that
  feed the trace pane — no extra hooks into the agent
- slash commands for sessions, trace, cost, clear
- escape cancels a running turn; sessions persist and replay on startup

Everything runs inside the `scratch` workspace, same as the demos.
"""

import sys
import threading
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # so `harness`/`model` resolve when run directly

from rich.markdown import Markdown as RichMarkdown
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, Label, RichLog, Static

from harness.agent import Agent
from harness.sessions import list_sessions
from harness.tools import strip_thought
from harness.tracer import Tracer

HELP = """\
**Commands**

- `/help` — this list
- `/new [name]` — start a fresh session
- `/sessions` — list saved sessions
- `/open <name>` — resume a saved session
- `/trace` — toggle the trace pane
- `/cost` — tokens and cost so far
- `/model` — provider chain and current model
- `/clear` — clear the screen (history is kept)
- `/quit` — exit

**Keys** — `escape` cancel turn · `ctrl+t` trace pane · `ctrl+l` clear · `ctrl+c` quit
"""


class Cancelled(Exception):
    """Raised from the token callback when the user hits escape. It is not in
    any retry bucket, so it propagates straight out of the client instead of
    being mistaken for a transient failure."""


class StreamView:
    """Decides what a human should SEE while tokens are still arriving.

    Raw deltas are not fit for display: Gemma opens with a <thought> block, and
    a tool call is a wall of JSON. Both are correct output and both are noise on
    screen, so we accumulate the raw text and render a cleaned view of it.
    """

    def __init__(self):
        self.raw = ""

    def push(self, delta):
        self.raw += delta
        return self.render()

    def render(self):
        # An opened-but-unclosed thought block: the model is still reasoning.
        if "<thought>" in self.raw and "</thought>" not in self.raw:
            return "thinking..."

        visible = strip_thought(self.raw).strip()
        if not visible:
            return "thinking..."

        # A tool call starts as JSON (sometimes fenced). Streaming
        # {"tool": "bash", "args": {... to a chat pane helps nobody.
        if visible.startswith("{") or visible.startswith("```"):
            return "preparing tool call..."

        return visible

    def is_tool_call(self):
        visible = strip_thought(self.raw).strip()
        return visible.startswith("{") or visible.startswith("```")


class UserMessage(Static):
    def __init__(self, text):
        super().__init__(f"› {text}")


class AssistantMessage(Static):
    """Plain text while streaming (cheap), markdown once finalized (pretty)."""

    def finalize(self, text):
        self.update(RichMarkdown(text) if text.strip() else "(no reply)")


class ToolCard(Static):
    """A completed tool call, rendered from a tracer span."""

    def __init__(self, name, args, result):
        args_text = ", ".join(f"{k}={v!r}" for k, v in (args or {}).items())
        if len(args_text) > 80:
            args_text = args_text[:80] + "..."
        result_text = str(result).replace("\n", " ")
        if len(result_text) > 100:
            result_text = result_text[:100] + "..."
        super().__init__(f"[{name}] {args_text}\n  → {result_text}")


class SystemNote(Static):
    def __init__(self, text, markdown=False):
        super().__init__(RichMarkdown(text) if markdown else text)


class ApprovalModal(ModalScreen[bool]):
    """The approval gate as a dialog instead of a blocking console prompt."""

    BINDINGS = [("escape", "deny", "Deny")]

    def __init__(self, name, args):
        super().__init__()
        self.tool_name, self.tool_args = name, args

    def compose(self) -> ComposeResult:
        with Vertical(id="approval-box"):
            yield Label("Approve this tool call?", id="approval-title")
            body = "\n".join(f"{k} = {v!r}" for k, v in (self.tool_args or {}).items())
            yield Static(f"{self.tool_name}\n\n{body}", id="approval-body")
            with Horizontal(id="approval-buttons"):
                yield Button("Allow", id="allow", variant="success")
                yield Button("Deny", id="deny", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "allow")

    def action_deny(self) -> None:
        self.dismiss(False)


class HarnessApp(App):
    TITLE = "harness"

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+l", "clear", "Clear"),
        ("ctrl+t", "toggle_trace", "Trace"),
        ("escape", "cancel", "Cancel turn"),
    ]

    CSS = """
    #body { height: 1fr; }
    #transcript { width: 1fr; padding: 0 2; }
    #trace-pane { width: 46; border-left: solid $panel; padding: 0 1; }
    #status { height: 1; background: $panel; color: $text-muted; padding: 0 1; }
    #chat-input { border: tall $accent; }

    UserMessage { color: $accent; text-style: bold; margin: 1 0 0 0; }
    AssistantMessage { margin: 0 0 1 0; }
    ToolCard {
        color: $text-muted; border-left: solid $warning;
        padding: 0 1; margin: 0 0 1 1;
    }
    SystemNote { color: $text-muted; margin: 1 0; }

    #approval-box {
        width: 70; height: auto; padding: 1 2;
        border: thick $warning; background: $surface;
    }
    #approval-title { text-style: bold; }
    #approval-body { margin: 1 0; color: $text-muted; }
    #approval-buttons { height: auto; align-horizontal: right; }
    #approval-buttons Button { margin-left: 1; }
    """

    def __init__(self, session="tui"):
        super().__init__()
        self.session_name = session
        self.tracer = Tracer(sinks=[self._trace_sink])
        self.agent = self._build_agent(session)

        self.stream_view = None       # display filter for the turn in flight
        self.current_msg = None       # AssistantMessage being streamed into
        self.cancel_requested = False
        self.busy = False
        self.total_tokens = 0
        self.total_cost = 0.0

    # ---- setup ----------------------------------------------------------

    def _build_agent(self, session):
        return Agent(
            workspace="scratch",
            approver=self._tui_approver,
            tracer=self.tracer,
            on_token=self._on_token,   # the only streaming call site in the project
            session=session,
        )

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="body"):
            yield VerticalScroll(id="transcript")
            yield RichLog(id="trace-pane", wrap=True, markup=False)
        yield Static("", id="status")
        yield Input(placeholder="Message the agent…  (/help for commands)", id="chat-input")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#trace-pane").display = False
        self._refresh_status()
        self._replay_history()
        self.query_one("#chat-input", Input).focus()

    def _replay_history(self):
        """Resuming a session should look like resuming a conversation, not an
        empty screen with hidden state. Skips the system prompt and the
        synthetic tool-result messages the loop feeds back to the model."""
        shown = 0
        for message in self.agent.messages:
            role, content = message.get("role"), message.get("content", "")
            if role == "system" or content.startswith("[tool result for"):
                continue
            if role == "user":
                self._mount(UserMessage(content))
            else:
                widget = AssistantMessage()
                self._mount(widget)
                widget.finalize(strip_thought(content).strip())
            shown += 1
        if shown:
            self._mount(SystemNote(f"— resumed session '{self.session_name}' ({shown} messages) —"))

    # ---- small helpers --------------------------------------------------

    def _mount(self, widget):
        transcript = self.query_one("#transcript", VerticalScroll)
        transcript.mount(widget)
        transcript.scroll_end(animate=False)

    def _refresh_status(self):
        model = self.agent.client.last_model or self.agent.client.model
        state = "working…" if self.busy else "ready"
        self.query_one("#status", Static).update(
            f" {state}  ·  session: {self.session_name}  ·  {model}"
            f"  ·  {self.total_tokens:,} tokens  ·  ${self.total_cost:.4f}"
        )

    # ---- callbacks from the agent's worker thread -----------------------

    def _on_token(self, delta):
        """One streamed chunk. Runs on the worker thread."""
        if self.cancel_requested:
            raise Cancelled()
        if self.stream_view is None:
            return
        text = self.stream_view.push(delta)
        self.call_from_thread(self._render_stream, text)

    def _render_stream(self, text):
        if self.current_msg is None:
            self.current_msg = AssistantMessage()
            self._mount(self.current_msg)
        self.current_msg.update(text)
        self.query_one("#transcript", VerticalScroll).scroll_end(animate=False)

    def _trace_sink(self, span):
        """Every span goes to the trace pane. Tool spans ALSO become cards in
        the transcript — the tracer we built in Ch 13 turns out to be exactly
        the event stream a UI needs, so no new agent hooks were required."""
        attrs = " ".join(f"{k}={v}" for k, v in span.attributes.items())
        self.call_from_thread(
            self.query_one("#trace-pane", RichLog).write,
            f"{span.kind:9s} {span.name:10s} {span.duration_s:5.2f}s  {attrs}",
        )

        if span.kind == "llm_call":
            self.total_tokens += span.attributes.get("tokens") or 0
            self.total_cost += span.attributes.get("cost") or 0.0
            self.call_from_thread(self._refresh_status)
        elif span.kind == "tool_call":
            self.call_from_thread(
                self._show_tool_card,
                span.name,
                span.attributes.get("args"),
                span.attributes.get("result"),
            )

    def _show_tool_card(self, name, args, result):
        """A tool ran, so the streamed JSON that requested it is now noise —
        replace that placeholder with the tool card itself."""
        if self.current_msg is not None:
            self.current_msg.remove()
            self.current_msg = None
        if self.stream_view is not None:
            self.stream_view = StreamView()   # next model turn starts clean
        self._mount(ToolCard(name, args, result))

    def _tui_approver(self, name, args):
        """Runs on the worker thread; blocks on an Event while the modal is
        shown and answered on the UI thread."""
        result = {}
        done = threading.Event()

        def show_modal():
            def handle(approved):
                result["approved"] = approved
                done.set()
            self.push_screen(ApprovalModal(name, args), handle)

        self.call_from_thread(show_modal)
        done.wait()
        return result.get("approved", False)

    # ---- input ----------------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return
        if text.startswith("/"):
            self._run_command(text)
            return
        if self.busy:
            self._mount(SystemNote("still working — press escape to cancel"))
            return
        self._mount(UserMessage(text))
        self._start_turn(text)

    def _start_turn(self, text):
        self.busy = True
        self.cancel_requested = False
        self.stream_view = StreamView()
        self.current_msg = None
        self._refresh_status()
        self._run_agent(text)

    @work(thread=True)
    def _run_agent(self, text: str) -> None:
        """agent.run() off the UI thread, so streaming, modals and trace
        updates all render while it works."""
        try:
            reply = self.agent.run(text)
            clean = strip_thought(reply).strip()
            self.call_from_thread(self._finish_turn, clean)
        except Cancelled:
            self.call_from_thread(self._finish_turn, None, "— cancelled —")
        except Exception as e:  # surface failures in the chat, never silently
            self.call_from_thread(self._finish_turn, None, f"— {type(e).__name__}: {e} —")

    def _finish_turn(self, reply, note=None):
        if reply is not None:
            if self.current_msg is None:
                self.current_msg = AssistantMessage()
                self._mount(self.current_msg)
            # The reply is the same accumulated string streaming already showed;
            # re-rendering it as markdown is the only difference.
            self.current_msg.finalize(reply)
        elif self.current_msg is not None:
            self.current_msg.remove()

        if note:
            self._mount(SystemNote(note))

        self.current_msg = None
        self.stream_view = None
        self.busy = False
        self._refresh_status()
        self.query_one("#transcript", VerticalScroll).scroll_end(animate=False)

    # ---- slash commands -------------------------------------------------

    def _run_command(self, text):
        parts = text.split()
        command, args = parts[0].lower(), parts[1:]

        if command == "/help":
            self._mount(SystemNote(HELP, markdown=True))
        elif command == "/quit":
            self.exit()
        elif command == "/clear":
            self.action_clear()
        elif command == "/trace":
            self.action_toggle_trace()
        elif command == "/cost":
            self._mount(SystemNote(
                f"{self.total_tokens:,} tokens · ${self.total_cost:.4f} "
                f"(free tier — see model/pricing.py)"
            ))
        elif command == "/model":
            client = self.agent.client
            self._mount(SystemNote(
                f"chain: {' → '.join(client.providers)}\n"
                f"last served by: {client.last_provider or '—'} / {client.last_model or '—'}"
            ))
        elif command == "/sessions":
            rows = list_sessions()
            if not rows:
                self._mount(SystemNote("no saved sessions yet"))
            else:
                lines = "\n".join(
                    f"  {name:<20} {count:>4} msgs   "
                    f"{datetime.fromtimestamp(mtime):%Y-%m-%d %H:%M}"
                    for name, count, mtime in rows
                )
                self._mount(SystemNote(f"saved sessions:\n{lines}"))
        elif command in ("/new", "/open"):
            if command == "/new":
                name = args[0] if args else f"tui-{datetime.now():%Y%m%d-%H%M%S}"
            elif not args:
                self._mount(SystemNote("usage: /open <session-name>"))
                return
            else:
                name = args[0]
            self._switch_session(name)
        else:
            self._mount(SystemNote(f"unknown command {command} — try /help"))

    def _switch_session(self, name):
        self.session_name = name
        self.agent = self._build_agent(name)
        self.query_one("#transcript", VerticalScroll).remove_children()
        self._replay_history()
        self._mount(SystemNote(f"— session: {name} —"))
        self._refresh_status()

    # ---- key actions ----------------------------------------------------

    def action_clear(self) -> None:
        """Clears the screen only. Conversation state is untouched — the model
        still remembers everything; you just stop looking at it."""
        self.query_one("#transcript", VerticalScroll).remove_children()
        self._mount(SystemNote("— screen cleared (history kept) —"))

    def action_toggle_trace(self) -> None:
        pane = self.query_one("#trace-pane")
        pane.display = not pane.display

    def action_cancel(self) -> None:
        if self.busy:
            self.cancel_requested = True


if __name__ == "__main__":
    HarnessApp().run()
