"""LLM client wrapper — the single doorway for every LLM call.

Now with retry and provider fallback, which are two different things:

- RETRY    = same provider, try again. For failures that are temporary.
- FALLBACK = next provider. For failures that mean this provider is unusable.

Conflating them is the classic mistake: retrying a malformed request three
times just wastes three seconds and hides your bug. So errors get sorted into
three buckets (see below), and each bucket is handled differently.

Because everything in the harness calls LLMClient.chat(), all of this lands
here without a single caller changing.
"""

import os
import time

from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)

load_dotenv()  # reads .env into environment variables (keys never live in code)

# Provider registry. Adding a new OpenAI-compatible backend = one more entry.
# Note default_model per provider: model ids do NOT transfer across providers.
# "gemma-4-31b-it" is a Google id; Groq has never heard of it. Falling back is
# not just swapping base_url — each provider needs its own model name.
PROVIDERS = {
    "google": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "env_key": "GOOGLE_API_KEY",
        "default_model": "gemma-4-31b-it",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "env_key": "GROQ_API_KEY",
        # Alternatives on Groq: openai/gpt-oss-20b (faster), qwen/qwen3.6-27b
        # (closest in size to the Gemma above). No Gemma on Groq as of 2026-07.
        "default_model": "openai/gpt-oss-120b",
    },
}

# --- the three buckets -----------------------------------------------------

# 1. Transient. Retry the SAME provider after a pause; fall back only if the
#    retries are exhausted.
RETRYABLE = (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError)

# 2. This provider is unusable, but another might work. Skip retries (a bad key
#    won't fix itself) and fall back immediately.
FALLBACK_NOW = (AuthenticationError,)

# 3. Everything else — BadRequestError, NotFoundError (unknown model id), etc.
#    These are OUR bug and would fail identically on every provider, so they are
#    neither retried nor fallen back from. They propagate, loudly. There is no
#    tuple for this bucket: not catching it IS the handling.

MAX_ATTEMPTS = 3       # per provider
BACKOFF_BASE = 1.0     # seconds, doubling: 3 attempts means 2 sleeps (1s, 2s)
REQUEST_TIMEOUT = 60.0  # per request; the SDK's own default is 600s (10 min)


class ProviderUnavailable(Exception):
    """Provider can't be used at all (e.g. its API key isn't in the env).
    Treated like bucket 2: skip it, try the next provider."""


class StreamInterrupted(Exception):
    """A stream failed AFTER tokens were already delivered to the caller.
    Deliberately outside the retry buckets: retrying would paint a second,
    different reply on top of text a human has already read."""


class AllProvidersFailed(Exception):
    """Every provider in the chain failed. Raised rather than returned as a
    string: a caller that appended "Error: 429" to messages[] would be feeding
    the agent a fake model reply."""


class LLMClient:
    """Wraps an ordered chain of providers behind a stable .chat() call."""

    def __init__(self, providers=("google", "groq"), model=None,
                 max_attempts=MAX_ATTEMPTS, backoff_base=BACKOFF_BASE, verbose=True):
        self.providers = list(providers)
        # An explicit model applies only to the FIRST provider — it's a Google
        # id if the chain starts with Google, so forcing it onto the fallback
        # would guarantee a 404. Fallbacks use their own default_model.
        self.model_override = model
        self.max_attempts = max_attempts
        self.backoff_base = backoff_base
        self.verbose = verbose

        self._clients = {}  # provider -> OpenAI, built lazily on first use
        self.model = model or PROVIDERS[self.providers[0]]["default_model"]

        # What actually served the most recent call. last_provider/last_model
        # matter for tracing: if the fallback answered, the trace must say so.
        self.last_usage = None
        self.last_provider = None
        self.last_model = None

    def _client_for(self, provider):
        """Build (and cache) the SDK client for a provider."""
        if provider not in self._clients:
            cfg = PROVIDERS[provider]
            key = os.environ.get(cfg["env_key"])
            if not key:
                raise ProviderUnavailable(f"{cfg['env_key']} not set")
            # max_retries=0: the SDK retries 429/5xx twice by default, which
            # would stack invisibly under our own retry loop (3 attempts would
            # mean 9 requests) AND rob us of the fallback decision. We own retry
            # policy here, so the transport layer must not have its own.
            # timeout: the SDK's default read timeout is 600s, which makes any
            # retry policy meaningless — one hung call blocks for ten minutes.
            self._clients[provider] = OpenAI(
                base_url=cfg["base_url"],
                api_key=key,
                max_retries=0,
                timeout=REQUEST_TIMEOUT,
            )
        return self._clients[provider]

    def _model_for(self, provider, index, per_call_model):
        """Which model id to use for this provider (see model_override note)."""
        if index == 0 and (per_call_model or self.model_override):
            return per_call_model or self.model_override
        return PROVIDERS[provider]["default_model"]

    def _log(self, message):
        if self.verbose:
            print(message)

    def chat(self, messages, model=None, on_token=None):
        """Send a messages list and return the assistant's reply text, walking
        the provider chain until one succeeds.

        `on_token`: optional callback fn(delta_text). When given, the reply is
        streamed and the callback fires per chunk. The RETURN VALUE is the same
        complete string either way — streaming is a presentation concern, so
        every internal caller (subagents, orchestrator, compaction, the tool
        loop) can ignore it entirely and keep working unchanged.
        """
        failures = []
        for index, provider in enumerate(self.providers):
            use_model = self._model_for(provider, index, model)
            try:
                return self._chat_one_provider(provider, use_model, messages, on_token)
            except (ProviderUnavailable,) + FALLBACK_NOW + RETRYABLE as e:
                # Bucket 1 (retries exhausted) or bucket 2 — try the next one.
                failures.append(f"{provider}: {type(e).__name__}")
                self._log(f"[fallback] {provider} unusable ({type(e).__name__}); trying next provider")
            # Bucket 3 is deliberately NOT caught — it propagates from here.

        raise AllProvidersFailed("; ".join(failures) or "no providers configured")

    def _chat_one_provider(self, provider, model, messages, on_token=None):
        """One provider, with retries on transient failures."""
        client = self._client_for(provider)

        for attempt in range(1, self.max_attempts + 1):
            try:
                if on_token:
                    reply = self._stream_once(client, provider, model, messages, on_token)
                else:
                    reply = self._call_once(client, provider, model, messages)
                return reply

            except StreamInterrupted:
                # Tokens were already shown to a human. Retrying would produce a
                # DIFFERENT reply on top of text they've already read, so this
                # one is not retryable no matter which attempt we're on.
                raise

            except RETRYABLE as e:
                if attempt == self.max_attempts:
                    raise  # give up on this provider; chat() decides about falling back
                delay = self.backoff_base * (2 ** (attempt - 1))
                self._log(
                    f"[retry] {provider}: {type(e).__name__} "
                    f"(attempt {attempt}/{self.max_attempts}), waiting {delay:.1f}s"
                )
                time.sleep(delay)

    def _call_once(self, client, provider, model, messages):
        """Plain, non-streaming request."""
        resp = client.chat.completions.create(model=model, messages=messages)
        if resp.usage:
            self.last_usage = resp.usage.total_tokens
        self.last_provider, self.last_model = provider, model
        return resp.choices[0].message.content

    def _stream_once(self, client, provider, model, messages, on_token):
        """Streaming request: fire on_token per chunk, accumulate, return the
        whole reply so callers see no difference in the return value."""
        # stream_options: without this the streaming API returns no usage object
        # at all, and last_usage would silently go stale — quietly degrading
        # compaction back to the chars/4 estimate.
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            stream_options={"include_usage": True},
        )

        chunks = []
        try:
            for event in stream:
                if event.usage:
                    self.last_usage = event.usage.total_tokens
                if not event.choices:
                    continue  # the final usage-only event carries no choices
                delta = event.choices[0].delta.content
                if delta:
                    chunks.append(delta)
                    on_token(delta)
        except RETRYABLE as e:
            if chunks:
                # Past the point of no return — a human has seen these tokens.
                raise StreamInterrupted(f"{type(e).__name__} after {len(chunks)} chunks") from e
            raise  # nothing shown yet, so a normal retry is still honest

        self.last_provider, self.last_model = provider, model
        return "".join(chunks)


if __name__ == "__main__":
    # Quick manual test:  uv run python -m model.client
    client = LLMClient()
    print(client.chat([{"role": "user", "content": "In one sentence, what is an agent harness?"}]))
    print(f"\n[served by {client.last_provider} / {client.last_model}]")
