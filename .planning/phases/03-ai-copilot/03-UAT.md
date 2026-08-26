---
status: testing
phase: 03-ai-copilot
source: [03-VERIFICATION.md]
started: 2026-08-25T21:55:00Z
updated: 2026-08-25T21:55:00Z
---

## Current Test

number: 1
name: Chat panel layout — right-hand sidebar that pushes content
expected: |
  Open the app, click the "AI Chat" toggle bottom-right. A ~384px-wide panel slides in from the
  right edge and PUSHES the watchlist/chart/positions/heatmap/P&L grid to the left (grid shrinks,
  does not get covered). The panel header shows "AI Chat" on the left and a "Close Chat" button on
  the right — no floating button overlapping the Send button anymore. Typing a message and
  clicking Send works without any click being intercepted.
awaiting: user response

## Tests

### 1. Chat panel layout — right-hand sidebar that pushes content
expected: |
  Open the app, click the "AI Chat" toggle bottom-right. A ~384px-wide panel slides in from the
  right edge and PUSHES the watchlist/chart/positions/heatmap/P&L grid to the left (grid shrinks,
  does not get covered). The panel header shows "AI Chat" on the left and a "Close Chat" button on
  the right — no floating button overlapping the Send button anymore. Typing a message and
  clicking Send works without any click being intercepted.
result: [pending]
note: |
  Originally specified (and shipped in 03-01/03-04) as a bottom-overlay drawer per CONTEXT.md
  decisions D-01/D-02. First UAT pass on that design found a real bug: the fixed "Close Chat"
  toggle sat on top of the Send button when the drawer was open, blocking clicks. Before that
  could be confirmed as fixed, the user requested a design change: move the panel to the right
  side and have it push/reflow the grid instead of overlaying it. Implemented both — the redesign
  structurally removes the overlap (the toggle now lives inside the panel header instead of
  floating over drawer content in every state) — re-verifying the new design in one pass rather
  than the old one.

### 2. Live (non-mock) LLM turn — grounding and tone
expected: |
  With OPENROUTER_API_KEY set and LLM_MOCK unset, ask the assistant to analyze the portfolio;
  separately run `uv run --directory backend python scripts/llm_smoke_check.py`. The reply's
  cash/position figures match the header/positions table exactly; structured-output parsing
  (response_format=ChatResponse) succeeds against the real Cerebras endpoint; tone is neutral and
  data-driven with no urgency/scarcity/shaming framing.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
