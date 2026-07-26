"""Demo: Ch 13 — observability. A calculation with a tracer attached: you'll
see a [trace] line per model call and per tool call, with duration, tokens,
and cost (free — we're on Google AI Studio's free tier).

Run (from the project root):  uv run python demos/demo_observability.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))  # so `from harness.agent import ...` finds the root

from harness.agent import Agent
from harness.tracer import Tracer, console_sink, jsonl_sink

tracer = Tracer(sinks=[console_sink, jsonl_sink("scratch/trace.jsonl")])
agent = Agent(workspace="scratch", tracer=tracer)

print("You: what is 256 / 8? Use the calculator tool.")
print("Bot:", agent.run("What is 256 / 8? Use the calculator tool."))

print(f"\n[{len(tracer.spans)} spans recorded — also written to scratch/trace.jsonl]")
