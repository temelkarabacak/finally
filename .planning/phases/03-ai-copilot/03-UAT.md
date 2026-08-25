---
status: testing
phase: 03-ai-copilot
source: [03-VERIFICATION.md]
started: 2026-08-25T21:55:00Z
updated: 2026-08-25T21:55:00Z
---

## Current Test

number: 1
name: Chat drawer visual overlay and non-reflow behavior
expected: |
  Open the app, click the AI Chat toggle bottom-right, confirm the drawer slides up from the
  bottom without reflowing the watchlist/chart/positions/heatmap/P&L grid, and the toggle label
  swaps between "AI Chat" and "Close Chat". Matches 03-01 Task 3's human-check steps 1-5 (drawer
  overlay, alignment, header styling, long-message wrapping, internal scroll).
awaiting: user response

## Tests

### 1. Chat drawer visual overlay and non-reflow behavior
expected: |
  Open the app, click the AI Chat toggle bottom-right, confirm the drawer slides up from the
  bottom without reflowing the watchlist/chart/positions/heatmap/P&L grid, and the toggle label
  swaps between "AI Chat" and "Close Chat". Matches 03-01 Task 3's human-check steps 1-5 (drawer
  overlay, alignment, header styling, long-message wrapping, internal scroll).
result: [pending]

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
