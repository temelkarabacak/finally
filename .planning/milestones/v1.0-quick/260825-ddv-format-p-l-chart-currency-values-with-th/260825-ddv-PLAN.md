---
phase: 260825-ddv
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - frontend/lib/format.ts
  - frontend/components/PnlChart.tsx
  - frontend/app/page.tsx
autonomous: true
requirements: [QUICK-260825-ddv]

estimate:
  tokens: 22000
  raw_tokens: 22000
  tasks: 2
  confidence: low

must_haves:
  truths:
    - "The P&L chart's right price-scale tick labels render a value of 10000 as `10,000.00` instead of `10000.00`."
    - "The P&L chart's crosshair price label uses the same thousands-separated formatting as the tick labels."
    - "The header's Total Value and Cash readouts render thousands separators (e.g. `Total Value 10,000.00`)."
    - "No numeric value, API response, chart series data, styling, or layout changes — only the rendered string form of already-displayed numbers."
  artifacts:
    - "frontend/lib/format.ts exporting `formatCurrency(value: number): string`"
  key_links:
    - "PnlChart's `createChart` options object includes a `localization.priceFormatter` entry bound to `formatCurrency`."
    - "app/page.tsx imports `formatCurrency` from `@/lib/format` and uses it for the two header readouts in place of bare `.toFixed(2)` calls."
---

<objective>
Add thousands-separator formatting to the currency values rendered by the P&L chart and the
portfolio header, so `10000.00` displays as `10,000.00`.

Purpose: Four- and five-figure portfolio values are the default state of this app (seed cash is
$10,000), and unseparated digit runs are hard to scan in a data-dense terminal UI.
Output: A single shared `formatCurrency` helper, wired into `PnlChart`'s Lightweight Charts price
scale and into the two header readouts in `app/page.tsx`.

Explicitly out of scope: backend formatting, API response shapes, `PriceChart.tsx` (per-share
quote axis), `PositionsTable.tsx`, `PortfolioHeatmap.tsx`, `WatchlistPanel.tsx`, and adding any
currency symbol that is not already rendered.
</objective>

<execution_context>
@/home/tamer/AICouseProjects/finally/.claude/gsd-core/workflows/execute-plan.md
@/home/tamer/AICouseProjects/finally/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md

@frontend/components/PnlChart.tsx
@frontend/app/page.tsx
@frontend/AGENTS.md
</context>

<interface_notes>
Verified against the installed `lightweight-charts@5.2.1` typings in
`frontend/node_modules/lightweight-charts/dist/typings.d.ts`:

- `ChartOptionsBase.localization: LocalizationOptionsBase` (line 1008) is a valid top-level key
  in the object passed to `createChart`.
- `LocalizationOptionsBase.priceFormatter?: PriceFormatterFn` (line 3372). Its own doc comment
  states it overrides "the price scale tick marks, labels and crosshair labels" — one entry
  covers both surfaces named in the must-haves.
- `export type PriceFormatterFn = (priceValue: BarPrice) => string` (line 4864). `BarPrice` is a
  nominal-branded `number`, so a `(value: number) => string` function is assignable to it
  without a cast.

`frontend/tsconfig.json` maps `@/*` to `./*`, so a new file at `frontend/lib/format.ts` is
importable as `@/lib/format` with no config change.

The frontend has no test runner installed (`package.json` scripts are `dev`, `build`, `start`,
`lint`), so verification uses a standalone `node -e` assertion of the formatting contract plus
the real Next.js build, rather than a unit test file.
</interface_notes>

<tasks>

<task type="tracer">
  <name>Task 1: Shared currency formatter wired end-to-end into the P&amp;L chart price scale</name>
  <files>frontend/lib/format.ts, frontend/components/PnlChart.tsx</files>
  <action>
Create `frontend/lib/format.ts` as a new module. It holds one module-level
`Intl.NumberFormat` instance built with the fixed locale `en-US` and options
`minimumFractionDigits: 2` and `maximumFractionDigits: 2`, and exports a single function
`formatCurrency(value: number): string` that returns that instance's formatted output. Pin the
locale rather than passing `undefined` so the rendered separator is identical in the browser,
in the static export, and in the verification command below — the app's number rendering must
not vary with the viewer's browser language settings. Do not prepend a currency symbol: the
existing header and axis render bare numbers and this change must not alter that. Give the
module a one-line module docstring-style comment and a short JSDoc block on the export,
matching the terse comment style already used in `PnlChart.tsx`.

Then modify `frontend/components/PnlChart.tsx`. Import `formatCurrency` from `@/lib/format`
alongside the existing `@/hooks/usePortfolio` import. In the `createChart` options object
inside the first `useEffect`, add a top-level `localization` key whose value is an object with
a single `priceFormatter` entry set to `formatCurrency`. Place it as a sibling of the existing
`layout`, `grid`, `timeScale`, and `rightPriceScale` keys. Change nothing else in this file:
the series colour, line width, `ResizeObserver` wiring, `setData` effect, empty-state logic,
and all JSX and Tailwind classes stay exactly as they are.

This is the thin end-to-end slice — helper module through chart option through rendered axis
label — that proves the formatting path before it is reused anywhere else.
  </action>
  <verify>
    <automated>node -e "const f=new Intl.NumberFormat('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});const c=[[10000,'10,000.00'],[10000.5,'10,000.50'],[999,'999.00'],[1234567.891,'1,234,567.89'],[-2500,'-2,500.00']];for(const [i,e] of c){const g=f.format(i);if(g!==e){console.error('FAIL',i,g,e);process.exit(1)}}console.log('format contract OK')"</automated>
    <automated>test -f frontend/lib/format.ts &amp;&amp; grep -q 'export function formatCurrency' frontend/lib/format.ts &amp;&amp; grep -q "priceFormatter: formatCurrency" frontend/components/PnlChart.tsx &amp;&amp; grep -q "@/lib/format" frontend/components/PnlChart.tsx &amp;&amp; echo "wiring OK"</automated>
  </verify>
  <done>
`frontend/lib/format.ts` exists and exports `formatCurrency`. The `en-US` two-decimal
`Intl.NumberFormat` contract produces `10,000.00` for `10000` and holds for the sub-thousand,
millions, and negative cases. `PnlChart.tsx` passes `formatCurrency` as
`localization.priceFormatter` to `createChart`, and no other line of `PnlChart.tsx` differs
from its prior state.
  </done>
</task>

<task type="auto">
  <name>Task 2: Apply the formatter to the header Total Value and Cash readouts</name>
  <files>frontend/app/page.tsx</files>
  <action>
In `frontend/app/page.tsx`, import `formatCurrency` from `@/lib/format` alongside the existing
`@/components/*` and `@/hooks/*` imports.

Replace the two header currency expressions with calls to `formatCurrency`, keeping the
surrounding label text, the `"--"` fallback for the null-portfolio case, the conditional
structure, and every Tailwind class byte-identical:

- The `Total Value` span currently formats `portfolio.total_value` with a bare two-decimal call;
  route that same value through `formatCurrency` instead.
- The `Cash` span currently formats `portfolio.cash_balance` the same way; route it through
  `formatCurrency` instead.

Leave the third span alone in its entirety: the connection-status dot, the status text, and the
selected-ticker quote appended to it are a per-share quote, not a portfolio total, and are out
of scope for this change. Do not touch `TradeBar`, `PositionsTable`, `PortfolioHeatmap`,
`WatchlistPanel`, `PriceChart`, the grid layout, or the `PnlChart` props.
  </action>
  <verify>
    <automated>grep -c "formatCurrency(portfolio\." frontend/app/page.tsx | grep -qx 2 &amp;&amp; grep -q "@/lib/format" frontend/app/page.tsx &amp;&amp; echo "header wiring OK"</automated>
    <automated>npm --prefix frontend run build</automated>
    <human-check>Load the app, confirm the header reads `Total Value 10,000.00` / `Cash 10,000.00` on a fresh portfolio, and that the P&amp;L chart's right-hand axis labels and crosshair label show comma-separated values once at least two snapshots exist. Confirm the watchlist, positions table, heatmap, price chart, and trade bar are visually unchanged.</human-check>
  </verify>
  <done>
The header renders both portfolio readouts through `formatCurrency`, `npm run build` completes
the Next.js static export with no TypeScript or lint-blocking errors, and no component other
than `PnlChart.tsx` and `app/page.tsx` has been modified.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| backend `/api/portfolio` → browser | Portfolio numbers cross into the React tree; this change only alters how already-rendered numbers are stringified, and introduces no new boundary. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-260825-ddv-01 | Tampering | `frontend/lib/format.ts` | low | mitigate | `formatCurrency` returns a plain string rendered as a React text child, so React's default escaping applies; no `dangerouslySetInnerHTML` and no DOM string injection is introduced. Lightweight Charts renders the `priceFormatter` result onto a canvas, not into HTML. |
| T-260825-ddv-02 | Information Disclosure | header readouts, P&L axis | low | accept | The values displayed are unchanged — only their separator formatting differs. No previously hidden data becomes visible. |
| T-260825-ddv-03 | Denial of Service | `Intl.NumberFormat` in `priceFormatter` | low | mitigate | The formatter instance is constructed once at module scope, not per call, so the per-tick price-scale formatting path allocates nothing new on the chart's render hot path. |

No package-manager installs occur in this plan (`Intl` is a platform built-in and
`lightweight-charts@5.2.1` is already a declared dependency), so no package-legitimacy gate
applies.
</threat_model>

<verification>
- `node -e` contract assertion passes for the thousands, sub-thousand, millions, and negative cases.
- `npm --prefix frontend run build` succeeds (covers `tsc` type-checking of the new `@/lib/format` import in both consumers and the static export).
- `git diff --stat` shows exactly three paths touched: `frontend/lib/format.ts` (new), `frontend/components/PnlChart.tsx`, `frontend/app/page.tsx`.
- `git diff frontend/components/PnlChart.tsx` shows only the added import and the added `localization` option — no changes to series config, effects, or JSX.
</verification>

<success_criteria>
- `10000` renders as `10,000.00` in the P&L chart price-scale tick labels, the P&L crosshair label, and the header Total Value and Cash readouts.
- No backend file, API response shape, or non-P&L frontend component is modified.
- The Next.js static export builds clean.
</success_criteria>

<output>
Create `.planning/quick/260825-ddv-format-p-l-chart-currency-values-with-th/260825-ddv-SUMMARY.md` when done
</output>
