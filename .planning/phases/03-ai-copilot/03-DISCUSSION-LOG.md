# Phase 3: AI Copilot - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-25
**Phase:** 3-AI Copilot
**Areas discussed:** Chat panel placement & collapse, Inline action confirmations, Chat starter experience, Timeout / retry UX, Rejected trade messaging, Mock mode demo behavior

---

## Chat panel placement & collapse

| Option | Description | Selected |
|--------|-------------|----------|
| Right sidebar | Fixed-width column on the right edge, full height — matches Bloomberg-style terminal copilots | |
| Bottom drawer | Slides up from the bottom, full width | ✓ |
| Left sidebar | Fixed-width column on the left, pushes grid right | |

**User's choice:** Bottom drawer

| Option | Description | Selected |
|--------|-------------|----------|
| Push (reflow) | Panel takes real layout space; grid resizes when chat opens/closes | |
| Overlay (float) | Panel slides over the grid as a fixed-position overlay; grid never resizes | ✓ |

**User's choice:** Overlay (float)

| Option | Description | Selected |
|--------|-------------|----------|
| Collapsed by default | Full trading grid first, chat opened via toggle | ✓ |
| Open by default | Chat visible immediately on load | |

**User's choice:** Collapsed by default
**Notes:** None.

---

## Inline action confirmations

| Option | Description | Selected |
|--------|-------------|----------|
| Summary card | Small bordered card inline in the chat bubble: ticker, side, quantity, fill price | ✓ |
| Colored pill/badge | Compact badge reusing green/red up/down convention | |
| Plain sentence | Confirmation as part of natural-language reply text | |

**User's choice:** Summary card

| Option | Description | Selected |
|--------|-------------|----------|
| Same treatment as trades | Reuse card/pill style for watchlist changes too | |
| Simpler — plain text only | Watchlist changes are lower-stakes, plain sentence is enough | ✓ |

**User's choice:** Simpler — plain text only
**Notes:** None.

---

## Chat starter experience

| Option | Description | Selected |
|--------|-------------|----------|
| Suggested quick-prompts | Clickable starter buttons above an empty input | ✓ |
| Empty input only | Just a placeholder, no history | |
| Greeting message | Canned assistant message, no clickable prompts | |

**User's choice:** Suggested quick-prompts

| Option | Description | Selected |
|--------|-------------|----------|
| Send immediately | One click sends the message | ✓ |
| Fill input, don't send | Click populates the text box for editing | |

**User's choice:** Send immediately
**Notes:** None.

---

## Timeout / retry UX

| Option | Description | Selected |
|--------|-------------|----------|
| Error bubble in thread | Appears as an assistant-style message bubble | ✓ |
| Toast/banner | Transient notification outside the message thread | |

**User's choice:** Error bubble in thread

| Option | Description | Selected |
|--------|-------------|----------|
| Stays in input | Failed message text remains in the input box | ✓ |
| Cleared | Input resets after send regardless of outcome | |

**User's choice:** Stays in input
**Notes:** None.

---

## Rejected trade messaging

| Option | Description | Selected |
|--------|-------------|----------|
| Plain text in the reply | Conversational prose explains the rejection | |
| Same summary card, marked failed | Reuses trade card, styled failed (red border/label) | ✓ |

**User's choice:** Same summary card, marked failed
**Notes:** None.

---

## Mock mode demo behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Pattern-recognizing mock | Keyword/rule-based matcher so mock mode can demo/test trade execution paths | ✓ |
| Fixed canned response | Same deterministic message/JSON regardless of input | |

**User's choice:** Pattern-recognizing mock
**Notes:** Chosen to give TEST-02/03/04 and Phase 4's E2E "AI chat with inline trade" scenario real paths to exercise without a live API call. Exact pattern rules left to planner/researcher.

---

## Claude's Discretion

- Message bubble styling (alignment, color-coding) — offered in round 2 but not selected for discussion.
- System prompt wording/tone — already specified by PLAN.md §9.
- Exact mock-mode pattern rules (which keywords map to which mock trades/responses).
- `uv add litellm pydantic` dependency addition — mechanical.
- Chat message DB write ordering/transaction discipline — backend implementation detail.

## Deferred Ideas

None — discussion stayed within phase scope.
