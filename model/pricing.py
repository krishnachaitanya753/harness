"""Pricing — cost from token usage.

A lookup table so cost comes from data, not scattered constants. Our models
are free-tier/open (Google AI Studio, Groq), so every rate here is 0 — but the
shape is ready for a real hosted metered model to slot in with nonzero rates.
"""

# model_name -> (cost per 1K input tokens, cost per 1K output tokens), USD.
PRICING = {
    # Google AI Studio (free tier)
    "gemma-4-31b-it": (0.0, 0.0),
    "gemma-4-26b-a4b-it": (0.0, 0.0),
    # Groq (free tier) — the fallback chain
    "openai/gpt-oss-120b": (0.0, 0.0),
    "openai/gpt-oss-20b": (0.0, 0.0),
    "qwen/qwen3.6-27b": (0.0, 0.0),
}


def estimate_cost(model, total_tokens):
    """Rough cost estimate. We only have a combined total_tokens count (not
    separate input/output) from this API's usage object, so this averages the
    two rates rather than pricing them separately — fine for free models
    where the answer is always 0, honest that it's approximate otherwise."""
    rate_in, rate_out = PRICING.get(model, (0.0, 0.0))
    return (total_tokens / 1000) * ((rate_in + rate_out) / 2)
