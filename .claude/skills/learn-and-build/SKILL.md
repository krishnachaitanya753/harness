---
name: learn-and-build
description: The teach-first incremental loop for this build-your-own-harness learning project. Use when Krishna wants to design, understand, or implement the next component of the agent harness, or says /learn-and-build. Enforces: explain before coding, one component at a time, only implement on explicit go, log lessons to memory.
---

# Learn-and-Build Loop

This project is a **learning** project: build a minimal agent harness in Python, one small piece at a
time, understanding each piece before moving on. This skill is the loop we run for every component.

## The loop

### 1. Orient
- Look at `MEMORY.md` and recent `memory/*.md` to recall what's already built and learned.
- Say in one or two lines: what exists now, and what the natural *next* smallest component is.

### 2. Teach + design (NO code yet)
- Explain the concept behind the next component: what problem it solves in a harness, and how it
  connects to what we've built. Keep it concrete and short.
- Sketch the design in prose or tiny pseudo-code: inputs, outputs, the key idea. Name the ~10–30
  lines we're about to write and why.
- If there's a real design fork (e.g. sync vs streaming, dict vs class), surface it and recommend one.
- Then **stop and wait**. Do not write files until Krishna explicitly approves ("go", "do it", etc.).

### 3. Implement (only after explicit go)
- Write the **smallest working version** of just this component. No extra features, no scaffolding
  for imagined future needs.
- Keep it readable and commented on the *why*. Match Python conventions already in the repo.
- Prefer something Krishna could re-type from memory over something impressive.

### 4. Verify + explain
- Show how to run/test it (PowerShell commands). Run it if that's useful and safe.
- Walk through what just happened, tying the code back to the concept from step 2.
- Invite questions / tweaks before moving on.

### 5. Log the lesson
- Append a `project`-type memory (progress) and, if a real concept was learned, a `reference`- or
  `project`-type memory capturing the insight in Krishna's terms.
- Add/refresh the one-line pointer in `MEMORY.md`.
- Convert any relative dates to absolute.

Then return to step 1 for the next component — but only when Krishna is ready.

## Guardrails
- Never jump ahead and build multiple components at once.
- Never write code before an explicit go, even if the design was approved — approval of a *design*
  is not approval to *write files* unless Krishna says so in the same breath.
- If Krishna asks "just show me" without committing, show a snippet in chat, don't create files.
- Keep every explanation tight; this is about understanding, not walls of text.
