"""Tools — a tool is just a function + a schema, kept in a registry.

The split that matters: the model decides WHAT to call and with what args; the
harness decides HOW/whether to run it, then actually runs it. The model never
touches your machine — it only emits a JSON request the harness dispatches.

Protocol (prompt-based, so it works with any model incl. open ones like Gemma):
we describe the tools in the system prompt (tool_instructions) and ask the model
to emit  {"tool": "<name>", "args": {...}}  when it wants one. The harness parses
that (parse_tool_call) and dispatches it (run_tool).
"""

import ast
import json
import operator
import re
from dataclasses import dataclass
from typing import Callable


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict          # {arg_name: human description} — the "schema"
    func: Callable            # func(args: dict, workspace) -> str
    requires_approval: bool = False


# ---- tool implementations -------------------------------------------------

# Safe arithmetic: evaluate a math expression WITHOUT eval(). Never eval() text
# that came from a model — it's untrusted input. We walk a small AST instead.
_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def _safe_eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("unsupported expression")


def calculator(args, workspace):
    """Evaluate a basic arithmetic expression (workspace unused)."""
    tree = ast.parse(args["expression"], mode="eval")
    return str(_safe_eval(tree.body))


def write_file(args, workspace):
    """Write text to a file, confined to the workspace."""
    path = workspace.resolve(args["path"])       # refuses escapes outside the root
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(args["content"], encoding="utf-8")
    return f"Wrote {len(args['content'])} chars to {args['path']}"


# ---- registry -------------------------------------------------------------

TOOLS = {
    "calculator": Tool(
        name="calculator",
        description="Evaluate a basic arithmetic expression, e.g. '12*(3+4)'.",
        parameters={"expression": "the arithmetic expression to evaluate"},
        func=calculator,
        requires_approval=False,   # safe → runs free
    ),
    "write_file": Tool(
        name="write_file",
        description="Write text to a file inside the workspace.",
        parameters={"path": "relative file path", "content": "text to write"},
        func=write_file,
        requires_approval=True,    # dangerous → hits the approval gate
    ),
}


def render_specs():
    """Human-readable tool list for the system prompt."""
    lines = []
    for t in TOOLS.values():
        args = ", ".join(f'"{k}": <{v}>' for k, v in t.parameters.items())
        gate = "  (requires approval)" if t.requires_approval else ""
        lines.append(f'- {t.name}: {t.description}{gate}\n    args: {{{args}}}')
    return "\n".join(lines)


def tool_instructions():
    """The protocol + specs we append to the system prompt."""
    return (
        "You have tools. To use one, reply with ONLY a JSON object and nothing else:\n"
        '{"tool": "<name>", "args": { ... }}\n'
        "After you get the tool result back, either call another tool the same way, "
        "or give your final answer as plain prose (no JSON).\n\n"
        "Available tools:\n" + render_specs()
    )


def run_tool(name, args, workspace):
    """Dispatch a tool call by name; never raises — returns an error string instead."""
    tool = TOOLS.get(name)
    if tool is None:
        return f"Error: unknown tool {name!r}"
    try:
        return tool.func(args, workspace)
    except Exception as e:  # a bad tool call shouldn't crash the whole loop
        return f"Error running {name}: {e}"


# ---- parsing the model's request -----------------------------------------

_THOUGHT = re.compile(r"<thought>.*?</thought>", re.DOTALL)


def parse_tool_call(text):
    """If `text` is a tool call, return {'tool':..., 'args':...}; else None.

    Gemma prepends a <thought>...</thought> block and sometimes ```json fences,
    so we strip those first, then pull out the first {...} and JSON-parse it.
    """
    cleaned = _THOUGHT.sub("", text).strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = re.sub(r"^json\s*", "", cleaned, flags=re.IGNORECASE).strip()

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if isinstance(obj, dict) and "tool" in obj:
        return {"tool": obj["tool"], "args": obj.get("args", {})}
    return None
