"""Demo: Ch 8 — secrets denylist + the scrubbed bash sandbox.

Two checks:
1. Direct workspace test (no LLM involved) proving .env is refused even
   though it sits INSIDE the workspace root — the gap we found and fixed.
2. An agentic bash call that checks whether GOOGLE_API_KEY leaked into the
   sandboxed subprocess's environment. It should NOT be there, because
   sandbox.py only forwards PATH/SYSTEMROOT/COMSPEC.

Run:  uv run python demo_sandbox.py
"""

from agent import Agent, console_approver

print("=== 1. secrets denylist (direct, no LLM) ===")
agent = Agent(workspace=".", approver=console_approver)
try:
    agent.workspace.resolve(".env")
    print("LEAK: .env was NOT refused (bug!)")
except ValueError as e:
    print("refused as expected ->", e)

print("\n=== 2. bash tool runs in a scrubbed environment ===")
print("You: check whether GOOGLE_API_KEY is visible inside a shell command.")
reply = agent.run(
    'Use the bash tool to run: python -c "import os; print(\'GOOGLE_API_KEY\' in os.environ)" '
    "and tell me what it printed."
)
print("Bot:", reply)
