"""Provider client wrapper — the single doorway for every LLM call.

Every other part of the harness calls chat(); nothing else talks to an API directly.
That lets us swap or add backends (Google, Groq, ...) by changing CONFIG, not logic.
"""

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()  # reads .env into environment variables (keys never live in code)

# Provider registry. Adding a new OpenAI-compatible backend = one more entry here.
# This is why the wrapper is "provider-agnostic": callers pick a name, not a URL.
PROVIDERS = {
    "google": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "env_key": "GOOGLE_API_KEY",
    },
    "groq": {  # ready for the later fallback lesson; needs GROQ_API_KEY in .env
        "base_url": "https://api.groq.com/openai/v1",
        "env_key": "GROQ_API_KEY",
    },
}


def chat(messages, model="gemma-4-31b-it", provider="google"):
    """Send chat messages to a model and return the reply text.

    messages: list of {"role": ..., "content": ...} dicts (the OpenAI format).
              This list is what will later grow each turn to give an agent memory.
    model:    which model to use. It's a parameter (not hardcoded) so later each
              agent can pick its own — big model for an orchestrator, cheap one
              for workers.
    provider: which entry in PROVIDERS to route through.
    """
    cfg = PROVIDERS[provider]
    api_key = os.environ[cfg["env_key"]]  # KeyError here means the key isn't set
    client = OpenAI(base_url=cfg["base_url"], api_key=api_key)

    resp = client.chat.completions.create(model=model, messages=messages)
    return resp.choices[0].message.content


if __name__ == "__main__":
    # Quick manual test:  python client.py
    reply = chat([{"role": "user", "content": "In one sentence, what is an agent harness?"}])
    print(reply)
