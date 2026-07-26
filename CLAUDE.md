# Project: Build-Your-Own Agent Harness (learning)

We are building a **minimal agent harness and multi-agent orchestrator from scratch, in Python**,
to *learn how harnesses work* — not to ship a product. Krishna is learning; the goal is understanding.

## How we work together (IMPORTANT — read every session)

This is a **teach-first, incremental** project. Follow these rules on every turn:

1. **One component at a time.** Never write the whole system at once. We build the smallest next
   meaningful piece, together.
2. **Only build when told.** Do NOT write or edit code until Krishna explicitly says to (e.g. "go",
   "do it", "implement this"). Design, explain, and discuss freely before that.
3. **Explain before (and while) implementing.** Every new piece comes with a short "why it exists
   and how it fits" explanation. Assume the goal is for Krishna to understand, then be able to write
   it himself. Prefer teaching the concept over just producing code.
4. **Keep it minimal.** Favor the simplest version that reveals the concept. No premature frameworks,
   no cleverness that hides the mechanism. Readability > completeness.
5. **Log what we learn.** After finishing a component (or learning something notable), record it in
   memory (see below) so it survives across sessions.

When Krishna types `/learn-and-build`, follow that skill's loop.

## Tech decisions

- **Language:** Python.
- **LLM backends:** cheap / open models — DeepSeek, Gemma, etc. Most expose an **OpenAI-compatible
  API**, so use the `openai` Python SDK and just swap `base_url` + `api_key` + model name. Design the
  harness to be **provider-agnostic** behind a thin client wrapper.
- **Keys:** never hardcode. Read from environment variables (`.env` + `python-dotenv` is fine).
- **Package manager: always use `uv`, never `pip`.** Install deps with `uv add <pkg>` (or
  `uv pip install -r requirements.txt`); run scripts with `uv run python <file>.py`. `uv run`
  auto-uses the project venv, so no manual activate step.
- **Platform:** Windows 11, PowerShell primary shell.

## Concepts we'll build toward (rough roadmap, not a commitment)

A harness is the loop around an LLM. Likely components, smallest-first:
1. Provider client wrapper (one function to call any OpenAI-compatible model).
2. A basic agent loop (prompt in → model out → done).
3. Tool calling (define tools, let the model request them, execute, feed results back).
4. The agent loop with tools (the real "harness": loop until the model stops asking for tools).
5. Memory / conversation state.
6. Multi-agent orchestration (a coordinator that spawns/directs sub-agents).
7. Extras as they come up: streaming, retries, token/cost tracking, structured output.

We pick the *next* item only when the current one is understood.

## Repo layout

Three packages, one dependency direction: **UI → harness → model**. Nothing points back up.

- `model/` — talking to LLM providers, nothing else. `client.py` (LLMClient), `pricing.py`.
  Has no idea an agent exists; that's what makes swapping providers cheap.
- `harness/` — the engine. `agent.py` (the loop), `context.py` (budgets + instructions +
  @refs + compaction), `tools.py` (registry + all tools), `workspace.py`/`sandbox.py`
  (security), `sessions.py`/`skills.py` (memory), `tracer.py`, `orchestrator.py`,
  `subagents.py`, `verify.py`.
- `ui/` — `tui.py`. The only package allowed to import `textual`.
- `demos/` — one runnable script per concept. `skills/` — skill *content* (SKILL.md), not code.

**Split a file into a folder only when it earns it** (~350+ lines, or two concerns inside it
change for different reasons). Folders with one small file are worse than one readable file.

## Repo conventions

- Keep files small and named for the concept they teach.
- Comment the *why*, not the obvious *what*.
- Progress and lessons live in memory (`MEMORY.md` index + `memory/*.md`).
