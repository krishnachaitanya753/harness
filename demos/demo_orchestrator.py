"""Demo: Ch 10 — the orchestrator plans a task into steps, then drives them.

A small multi-step calculation. Watch the plan get printed as a JSON-derived
list, then each step executed in order through the agent's normal run() loop
(unchanged) — the shape of a workflow, not one opaque turn.

Run (from the project root):  uv run python demos/demo_orchestrator.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))  # so `from harness.agent import ...` finds the root

from harness.agent import Agent, console_approver
from harness.orchestrator import Orchestrator


def plan_approver(steps):
    print("\n=== proposed plan ===")
    for i, step in enumerate(steps, start=1):
        print(f"  {i}. {step}")
    return input("approve this plan? (y/n): ").strip().lower().startswith("y")


agent = Agent(workspace="scratch", approver=console_approver)
orchestrator = Orchestrator(agent, plan_approver=plan_approver)

task = (
    "First calculate 12 * 3 using the calculator tool. Then add 10 to that "
    "result, also using the calculator tool. Then multiply the new total by 2, "
    "again using the calculator tool."
)

results = orchestrator.run(task)

print("\n=== final results ===")
for r in results:
    print(f"- {r['step']}\n  => {r['result']}")
