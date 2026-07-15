"""LLM client wrapper — the single doorway for every LLM call.

Now a class instead of a bare function: future features (streaming, tool-calling,
retries, provider fallback) become new methods or small tweaks *inside here*, so
the rest of the harness never has to change how it calls the model.
"""

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()  # reads .env into environment variables (keys never live in code)

# Provider registry. Adding a new OpenAI-compatible backend = one more entry here.
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


class LLMClient:
    """Wraps one provider + default model behind a stable .chat() call.

    Everything in the harness talks to an LLMClient, never to the OpenAI SDK
    directly, so swapping providers or adding behaviour stays local to this class.
    """

    def __init__(self, provider="google", model="gemma-4-31b-it"):
        cfg = PROVIDERS[provider]
        self.provider = provider
        self.model = model
        # Build the SDK client once and reuse it for every call.
        self._client = OpenAI(base_url=cfg["base_url"], api_key=os.environ[cfg["env_key"]])
        # Model-reported token count from the most recent call, if any. None
        # until the first response comes back — callers fall back to an
        # estimate until then.
        self.last_usage = None

    def chat(self, messages, model=None):
        """Send a messages list and return the assistant's reply text.

        `model` overrides the instance default per-call — useful later when one
        agent wants a bigger/smaller model for a single request.
        """
        resp = self._client.chat.completions.create(
            model=model or self.model,
            messages=messages,
        )
        if resp.usage:
            self.last_usage = resp.usage.total_tokens
        return resp.choices[0].message.content


if __name__ == "__main__":
    # Quick manual test:  uv run python client.py
    client = LLMClient()
    print(client.chat([{"role": "user", "content": "In one sentence, what is an agent harness?"}]))
