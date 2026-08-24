"""Pricing — cost from token usage.

A lookup table so cost comes from data, not scattered constants. Input and
output tokens are priced SEPARATELY because real providers charge 3-5x more for
output; averaging the two rates (which this used to do) produces a number that
looks precise and isn't.

Our models are free-tier/open, so every rate here is 0 — but the shape is right
for a metered model to slot in.
"""

# model_name -> (USD per 1K input tokens, USD per 1K output tokens)
PRICING = {
    # Google AI Studio (free tier)
    "gemma-4-31b-it": (0.0, 0.0),
    "gemma-4-26b-a4b-it": (0.0, 0.0),
    # Groq (free tier) — the fallback chain
    "openai/gpt-oss-120b": (0.0, 0.0),
    "openai/gpt-oss-20b": (0.0, 0.0),
    "qwen/qwen3.6-27b": (0.0, 0.0),
}


def estimate_cost(model, prompt_tokens=0, completion_tokens=0):
    """Cost for one call, pricing input and output at their own rates."""
    rate_in, rate_out = PRICING.get(model, (0.0, 0.0))
    return (prompt_tokens / 1000) * rate_in + (completion_tokens / 1000) * rate_out
