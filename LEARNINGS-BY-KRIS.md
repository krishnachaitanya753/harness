# Learnings by Kris

Non-obvious things found while building this harness — the kind that don't show up in
tutorials because everything *looks* like it works. Added as I hit them.

---

**1. Two retry layers stacked, and a 10-minute timeout nobody set.** I wrote retry +
fallback in `client.py`, then asked how many retries actually happen before falling
over to the next provider. The SDK's defaults made my answer fiction: `max_retries=2`
means it silently retries before raising to my code, so "3 attempts" was really up to
9 requests — and a 600s read timeout meant one hung call could block for ten minutes,
making any retry policy meaningless. Fixed with `max_retries=0, timeout=60.0`, since
my layer owns retry policy *and* the fallback decision. **Lesson:** when you add a
retry layer, check whether the library underneath already has one, and read its
default timeout while you're there.

**2. Model ids don't transfer between providers.** Hit twice — first when
`gemma-3-27b-it` didn't exist on Google AI Studio, then when `gemma-4-31b-it` meant
nothing to Groq (which no longer carries Gemma at all). Fixed with `default_model` per
provider, and an explicit `model=` that applies only to the first provider, since
forcing a Google id onto the fallback would 404 every time it fired. **Lesson:**
"OpenAI-compatible" is about the transport, not the catalogue — ask the API with
`client.models.list()` instead of trusting a doc or a memory.
