"""Subagents — a fresh agent for a self-contained subtask.

Ch 10's orchestrator drove multiple steps through ONE shared agent, so every
step piled into the same messages[] — a big job pollutes its own context.
The fix: give a subtask its OWN agent, own context, own tools, let it run to
completion, and keep only the final answer, not the transcript. Context
isolation is the feature, not a side effect.

Two tools ride on top of this: delegate (one subtask) and fan_out (a batch,
run in parallel — each subagent gets its own LLMClient so concurrent calls
don't race on shared state like LLMClient.last_usage).
"""

from concurrent.futures import ThreadPoolExecutor


def run_subagent(task, workspace=".", approver=None):
    """Build a fresh Agent, run the task to completion, return ONLY the reply.

    Lazy import: Agent's module imports tools.py, and tools.py wires in the
    delegate/fan_out tools defined here — importing Agent at module load time
    would be a circular import. Importing it inside the function breaks the
    cycle since by call time agent.py has finished loading.
    """
    from harness.agent import Agent
    sub = Agent(workspace=workspace, approver=approver)
    return sub.run(task)


def run_subagents_parallel(tasks, workspace=".", approver=None):
    """Fan out several independent subtasks in parallel. Order of results
    matches order of tasks, even though execution order may not."""
    with ThreadPoolExecutor(max_workers=len(tasks) or 1) as pool:
        futures = [pool.submit(run_subagent, t, workspace, approver) for t in tasks]
        return [f.result() for f in futures]
