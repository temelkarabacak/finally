@AGENTS.md

# Frontend — Developer Guide

Next.js 16 (App Router, Turbopack) + React 19 + Tailwind v4, built as a static export
(`output: "export"`) that FastAPI serves from `/`. One page, no router.

```bash
npm run dev        # dev server on :3100, proxies /api to the real backend on :8000
npm run mock       # standalone mock API on :8001 (see mock-server.mjs)
npm run dev:mock   # dev server pointed at the mock instead of the backend
npm test           # vitest + React Testing Library
npm run lint       # eslint (must stay clean)
npm run build      # static export -> out/
```

## Architecture

One React context, `TerminalProvider` (`hooks/useTerminal.tsx`), owns all shared state and is
the only thing that talks to the API. Components call `useTerminal()`; none of them fetch.

- **`hooks/usePriceStream.ts`** — the `EventSource` on `/api/stream/prices`. Ticks are buffered
  and flushed every 250ms so a burst of per-ticker events costs one render, not one each. It
  exposes `prices` (latest tick per ticker), `series` (up to 240 points per ticker, the source
  for sparklines and the main chart), `connection`, `tickCount`, `lastTickAt`.
- **`hooks/useTerminal.tsx`** — spreads the stream and adds `portfolio`, `watchlist`, `history`
  (REST, re-polled every 5s), the `selected` ticker, and the mutations `addTicker`,
  `removeTicker`, `trade` — each of which refetches on success. `priceOf(ticker)` prefers the
  live stream and falls back to the last REST value.
- **`lib/valuation.ts`** — `valuePortfolio(portfolio, priceOf)` remarks positions against live
  prices so the header and tables move at tick cadence, not at the 5s poll. Anything showing
  P&L should go through it rather than trusting `portfolio.positions` directly.
- **`lib/api.ts`** — every fetch, same-origin `/api/*`. Throws `ApiError` carrying the backend's
  `detail` so the UI can show rejection reasons verbatim (never clamp or reword them).
- **`hooks/useFlash.ts`** — returns `{className, seq}`; use `seq` as a React `key` to restart
  the CSS animation. Backed by `.flash-up` / `.flash-down` in `globals.css`.

## Components

| File | Role |
|---|---|
| `Header.tsx` | Live portfolio value, cash, unrealized P&L, connection dot |
| `StatusBar.tsx` | Feed telemetry plus a running tape of the latest ticks |
| `Panel.tsx` | The framed section every panel uses (`label`, `meta`, `actions`) |
| `Watchlist.tsx` | Symbol rows with sparkline, live price, change; add/remove; sets selection |
| `PriceChart.tsx` | Main chart for the selected symbol, from the SSE series |
| `PnlChart.tsx` | Total portfolio value over time from `/api/portfolio/history` |
| `Heatmap.tsx` | Treemap of positions, sized by weight, colored by P&L |
| `PositionsTable.tsx` | Qty, avg cost, last, value, P&L, P&L% — also sets selection |
| `TradeBar.tsx` | Market-order ticket; prefills from the selected symbol |
| `ChatPanel.tsx` | Collapsible AI sidebar; rehydrates from `/api/chat/history` |

`ChatPanel` disables its input and Send button until the history fetch settles (`historyLoaded`,
set in both the success and failure branches). The stored history *replaces* the message list, so
a message sent while that fetch is in flight would be silently discarded when it landed — the gate
removes the race structurally rather than timing around it. Real message bubbles carry
`data-testid="chat-bubble"`; the thinking indicator and the empty-state placeholder are sibling
`<li>`s inside the same `<ul>`, so count bubbles by testid, never by raw `li`.
| `PriceCell.tsx`, `Sparkline.tsx` | Shared price readout and trend line |

Charts are **Recharts** — keep it that way rather than mixing in a second library.

## Conventions

- Colors come from the `@theme` tokens in `app/globals.css` (`terminal`, `panel`, `edge`, `ink`,
  `amber`, `blue`, `violet`, `gain`, `loss`). Do not hardcode hex in components except where
  Recharts needs a literal string.
- The `num` utility class puts text in the mono face with tabular figures — every number uses it
  so digits do not shift as prices tick. `panel-label` is the small uppercase section label.
- Sign is always a non-color cue: `signedMoney` / `signedPercent` in `lib/format.ts`.
- Data displays render a sentence explaining what is missing rather than an empty box.

## Tests

`tests/` (vitest, jsdom, `vitest.config.mts`). `tests/setup.ts` stubs `EventSource` and
`ResizeObserver`, which jsdom lacks. Component tests mock `@/lib/api` wholesale and render
inside `TerminalProvider` with the fixtures in `tests/fixtures.ts`.

Covered: price flash direction, watchlist CRUD and error surfacing, positions P&L formatting and
tone, trade ticket submission/rejection, chat rendering, loading state, action chips, timeout, and
the history-load race described above.

Chat tests must go through the `openChat()` helper, which waits for the input to become enabled
before typing — typing into the gated input is a no-op and the test will fail confusingly.

## Known dev-only gotchas

- **Reach the dev server at `http://localhost:3100`, not `127.0.0.1`.** Next 16 blocks
  cross-origin dev resources and the page will load with its JS chunks 403'd.
- **SSE is buffered by the `next dev` rewrite proxy when the client sends `Accept-Encoding: gzip`**
  — the browser's `EventSource` then receives nothing while the connection still reports open.
  The fix is `Cache-Control: no-transform` on the SSE response; `mock-server.mjs` sets it. The
  real backend needs the same header for `npm run dev` against `:8000` to show a live feed. This
  is purely a dev-proxy artifact: production serves the export and the API from one origin with
  no proxy in between.
