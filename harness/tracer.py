"""Tracer — records every step of a run so a broken multi-step task doesn't
leave us driving blind.

The interesting bug is usually three tool calls earlier than the final
answer. A tracer runs alongside the loop and records a span per model call
and per tool call: how long it took, tokens, cost, and for tools, the exact
args in and result out.

One core, many consumers: record() fires each span once, and every registered
SINK gets it — console, a JSONL file, or (later) a UI panel. The core doesn't
know or care who's listening.
"""

import json
import time
from dataclasses import dataclass, field


@dataclass
class Span:
    kind: str          # "llm_call" | "tool_call"
    name: str
    duration_s: float
    attributes: dict = field(default_factory=dict)


def console_sink(span):
    attrs = " ".join(f"{k}={v}" for k, v in span.attributes.items())
    print(f"[trace] {span.kind:10s} {span.name:20s} {span.duration_s:.2f}s  {attrs}")


def jsonl_sink(path):
    """Returns a sink that appends each span to `path` as one JSON line."""
    def sink(span):
        record = {"kind": span.kind, "name": span.name, "duration_s": span.duration_s}
        record.update(span.attributes)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    return sink


class Tracer:
    """Records a span per model/tool call and fans it out to every sink."""

    def __init__(self, sinks=None):
        self.sinks = sinks if sinks is not None else [console_sink]
        self.spans = []

    def record(self, kind, name, duration_s, **attributes):
        span = Span(kind=kind, name=name, duration_s=duration_s, attributes=attributes)
        self.spans.append(span)
        for sink in self.sinks:
            sink(span)

    def timed(self, kind, name):
        """Context manager: `with tracer.timed("tool_call", name) as attrs:`
        — set attrs[...] inside the block, span is recorded on exit."""
        return _TimedSpan(self, kind, name)


class _TimedSpan:
    def __init__(self, tracer, kind, name):
        self.tracer, self.kind, self.name = tracer, kind, name
        self.attributes = {}

    def __enter__(self):
        self._start = time.monotonic()
        return self.attributes

    def __exit__(self, *exc_info):
        duration = time.monotonic() - self._start
        self.tracer.record(self.kind, self.name, duration, **self.attributes)
