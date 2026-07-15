---
name: social-image
description: Generate a bespoke SVG/PNG image built from real project data (progress bars, terminal-style flourishes, diagrams) for Krishna to share about this project. Use when he asks for a "cool image", "X card", "twitter/X image", "article header", or a graphic to post about the harness. Defaults to a normal, content-appropriate size — use the 5:2 X/Twitter header ratio ONLY when he explicitly asks for an X card, header, or says "5:2".
---

# Social image generation

Builds a real, data-driven graphic from the actual project (progress, architecture,
a specific fact) — not generic AI art. Same technique used for the first X card:
dark terminal-card aesthetic, real numbers, Claude's own color ramps.

## Sizing rule (read this first)

- **Default:** pick a size that fits the content and the stated destination —
  square (1080x1080) for a general share image, 16:9 (1200x675) for a blog/article
  embed, etc. Ask Krishna if the destination is unclear.
- **5:2 (1200x480 viewBox, exported at 2000x800)** ONLY when he explicitly asks for
  an "X card", "twitter header", "article header", or says "5:2". Don't default to
  it just because the first one we made was 5:2.

## Style bible (reuse across sizes)

- **Background:** dark warm charcoal `#1E1D17` (not pure black — matches the
  cream `#FAF9F5` used in this project's architecture diagrams, just inverted).
- **Title:** bold, off-white `#F7F5EE`, large (40-54px depending on canvas size).
- **Subtitle/body:** muted warm gray `#A9A79C`.
- **Terminal chip flourish:** a rounded rect (`fill #2B2A22 stroke #3D3C32`)
  containing 3 small colored dots (coral/amber/teal, mimicking mac terminal
  window controls) + a monospace command relevant to the content (e.g.
  `uv run python agent.py`). Adds authenticity — this is a real dev project,
  not stock art.
- **Data visual:** encode a REAL number from the project (components shipped,
  a metric, a count) as the graphic itself — bars, a staircase, dots — not a
  decorative shape. Reuse the color ramp: purple `#7F77DD`, teal `#5DCAA5`,
  coral `#F0997B`, pink `#ED93B1` (lighter/brighter stops for contrast on the
  dark background). "Built/done" items get solid fill; "planned/future" items
  get `fill="none" stroke="#6E6C63" stroke-dasharray="3 2"` outline-only.
- **Texture (optional, subtle):** one large faint glyph behind everything
  (`{ }`, `</>`, `>_`) at ~4% opacity, monospace, huge font-size — drawn FIRST
  in the SVG so it sits behind readable text.
- **Footer tagline:** small monospace line, muted color, a one-line takeaway
  (e.g. `agent = model + harness + UI`).

## Process

1. Confirm the destination/size with Krishna if not obvious (see sizing rule).
2. Write the SVG directly to the **scratchpad directory** (not the project
   repo — this is a shareable asset, not project source) via the Write tool.
   Use a viewBox matching the target ratio; set `width`/`height` attributes to
   ~2x the viewBox for a crisp export.
3. Render to PNG with headless Edge (no other rendering tool reliably available
   on this machine — cairosvg lacks its native lib here):
   ```
   EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
   [ -f "$EDGE" ] || EDGE="/c/Program Files/Microsoft/Edge/Application/msedge.exe"
   "$EDGE" --headless=new --disable-gpu --screenshot="<out.png>" \
     --window-size=<2x_viewbox_w>,<2x_viewbox_h> \
     --default-background-color=FF1E1D17 "file://<svg_path>"
   ```
4. Read the PNG back to verify it rendered cleanly (no clipped text, no
   overlapping elements) before sending.
5. Deliver both the `.svg` (editable) and `.png` via SendUserFile with
   `display: "render"` so it shows inline.

## Guardrails

- Real project data only — no invented numbers or generic decoration.
- Check text doesn't clip: compute label widths roughly before placing, leave
  margin from the canvas edge.
- Keep it flat (no gradients/shadows/blur) — matches the project's existing
  diagram style and renders reliably via headless-browser screenshot.
