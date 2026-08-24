"""Demo: retry + provider fallback, and the errors that deserve neither.

Three parts, one per error bucket:

1. Transient failure  -> retry the same provider, then fall back to the next.
2. Normal call        -> the chain's first provider just works.
3. Our own bug        -> raised immediately: no retries, no fallback, because
                         a bad model id fails identically everywhere.

Run (from the project root):  uv run python demos/demo_fallback.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))  # so `from model.client import ...` finds the root

from model.client import PROVIDERS, AllProvidersFailed, LLMClient

QUESTION = [{"role": "user", "content": "Reply with exactly: fallback worked"}]

# A deliberately broken provider. Port 9 (discard) refuses connections
# instantly, so we watch retries and backoff without waiting on real network
# timeouts. Injecting it here shows the registry is just data.
PROVIDERS["broken"] = {
    "base_url": "http://localhost:9/v1",
    "env_key": "GROQ_API_KEY",       # never actually used; we never connect
    "default_model": "irrelevant",
}

print("=== 1. transient failure: retry, then fall back to Groq ===")
client = LLMClient(providers=["broken", "groq"], backoff_base=0.5)
print("reply:", client.chat(QUESTION))
print(f"served by: {client.last_provider} / {client.last_model}")

print("\n=== 2. normal call: first provider answers, no fallback ===")
client = LLMClient()  # the real chain: google -> groq
print("reply:", client.chat(QUESTION))
print(f"served by: {client.last_provider} / {client.last_model}")

print("\n=== 3. our own bug: no retry, no fallback ===")
client = LLMClient(providers=["google", "groq"], model="no-such-model-exists")
try:
    client.chat(QUESTION)
    print("BUG: that should not have succeeded")
except AllProvidersFailed:
    print("BUG: fell back — a bad model id should not trigger fallback")
except Exception as e:
    print(f"raised straight through as {type(e).__name__} — correct, Groq would fail the same way")
