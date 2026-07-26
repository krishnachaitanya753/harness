"""Orchestrator — the control plane for multi-step tasks.

A single agent.run() call is one shot: ask, maybe some tool calls, one final
answer. A real task is a SEQUENCE of shots. The split, same as everywhere else
in this harness: the MODEL plans the steps (as JSON); the HARNESS drives them
— gates the plan, executes each step, retries a step that never finished.

Notice Agent itself doesn't change at all here. The orchestrator is just
something that calls agent.run(step) repeatedly, in order, on the SAME agent —
same messages[], same tools, same approval gate, same compaction. Every step
still shares one context window; that's the thing subagents fix next.

Honest limitation: we don't have real success/failure detection yet (that's
Ch 12, verification). "Retry on failure" here only means "retry a step that
hit the MAX_STEPS limit without a final answer" — not "retry until correct."
"""

import json
import re

_THOUGHT = re.compile(r"<thought>.*?</thought>", re.DOTALL)

PLAN_PROMPT = (
    "Break the following task into a short ordered list of concrete steps. "
    "Reply with ONLY a JSON array of strings, one per step, nothing else.\n\n"
    "Task: {task}"
)

MAX_RETRIES = 2


class Orchestrator:
    """Wraps an Agent to plan and drive a multi-step task through it."""

    def __init__(self, agent, plan_approver=None, max_retries=MAX_RETRIES):
        self.agent = agent
        self.plan_approver = plan_approver  # callable(steps: list[str]) -> bool
        self.max_retries = max_retries

    def plan(self, task):
        """Ask the model for an ordered list of step descriptions."""
        reply = self.agent.client.chat([{"role": "user", "content": PLAN_PROMPT.format(task=task)}])
        cleaned = _THOUGHT.sub("", reply).strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = re.sub(r"^json\s*", "", cleaned, flags=re.IGNORECASE).strip()

        match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if not match:
            return [task]  # couldn't parse a plan; fall back to the whole task as one step
        try:
            steps = json.loads(match.group(0))
        except json.JSONDecodeError:
            return [task]
        return [str(s) for s in steps if str(s).strip()]

    def run(self, task):
        """Plan the task, gate the plan once, then drive each step through the
        agent's normal run() loop. Returns [{'step', 'result'}, ...]."""
        steps = self.plan(task)

        if self.plan_approver and not self.plan_approver(steps):
            return [{"step": "(plan)", "result": "Plan rejected."}]

        results = []
        for i, step in enumerate(steps, start=1):
            print(f"\n[step {i}/{len(steps)}] {step}")
            result = self.agent.run(step)
            for attempt in range(1, self.max_retries + 1):
                if not result.startswith("Stopped:"):
                    break
                print(f"  retry {attempt}/{self.max_retries} (step never reached a final answer)...")
                result = self.agent.run(step)
            print(f"  -> {result}")
            results.append({"step": step, "result": result})

        return results
