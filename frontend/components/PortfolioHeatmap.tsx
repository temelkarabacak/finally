'use client';

import { ResponsiveContainer, Treemap } from "recharts";

import type { PositionView } from "@/hooks/usePortfolio";

type PortfolioHeatmapProps = {
  positions: PositionView[];
  loaded: boolean;
  selected: string | null;
  onSelect: (ticker: string) => void;
};

type HeatmapNode = {
  ticker: string;
  weight: number;
  pnl: number;
  pnlPercent: number;
};

const COLOR_UP = "#3fb950";
const COLOR_DOWN = "#f85149";
const COLOR_FLAT = "#8b949e";
const COLOR_STROKE = "#0d1117";
const COLOR_SELECTED = "#209dd7";
const COLOR_TEXT = "#e6edf3";

function fillFor(pnl: number): string {
  if (pnl > 0) return COLOR_UP;
  if (pnl < 0) return COLOR_DOWN;
  return COLOR_FLAT;
}

function signOf(value: number): string {
  return value >= 0 ? "+" : "";
}

/**
 * Recharts cell renderer for one treemap tile. Recharts injects layout
 * geometry (x, y, width, height, index) alongside the node's own fields, so
 * this reads both off the same props object (02-RESEARCH.md's
 * CustomizedCell pattern).
 */
function HeatmapCell(props: {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  ticker?: string;
  pnl?: number;
  pnlPercent?: number;
  selected: string | null;
  onSelect: (ticker: string) => void;
}) {
  const { x = 0, y = 0, width = 0, height = 0, ticker, pnl = 0, pnlPercent = 0, selected, onSelect } = props;
  if (!ticker) return null;

  const isSelected = selected === ticker;
  // Below a minimum readable size in either dimension, drop the label rather
  // than clip or overlap it against a neighbouring tile.
  const labelSuppressed = width < 24 || height < 24;
  const showLabel = !labelSuppressed;

  return (
    <g
      onClick={() => onSelect(ticker)}
      className="cursor-pointer"
      role="button"
      aria-label={`${ticker}: ${signOf(pnlPercent)}${pnlPercent.toFixed(2)}% unrealized P&L`}
    >
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        style={{
          fill: fillFor(pnl),
          stroke: isSelected ? COLOR_SELECTED : COLOR_STROKE,
          strokeWidth: isSelected ? 3 : 2,
        }}
      />
      {showLabel ? (
        <>
          <text x={x + 6} y={y + 18} fill={COLOR_TEXT} fontSize={12} fontFamily="var(--font-mono)">
            {ticker}
          </text>
          <text x={x + 6} y={y + 34} fill={COLOR_TEXT} fontSize={11} fontFamily="var(--font-mono)">
            {signOf(pnlPercent)}
            {pnlPercent.toFixed(2)}%
          </text>
        </>
      ) : null}
    </g>
  );
}

/**
 * Portfolio treemap: each tile sized by market value (share of total
 * holdings) and filled by the P&L sign, mirroring PositionsTable's colour
 * and selection conventions (02-UI-SPEC.md). Presentational only -- page.tsx
 * owns the fetch through usePortfolio and hands in already-revalued
 * positions.
 */
export function PortfolioHeatmap({ positions, loaded, selected, onSelect }: PortfolioHeatmapProps) {
  const showEmpty = positions.length === 0;

  const nodes: HeatmapNode[] = positions.map((position) => ({
    ticker: position.ticker,
    weight: position.market_value,
    pnl: position.unrealized_pnl,
    pnlPercent: position.unrealized_pnl_percent,
  }));

  return (
    <section
      className="flex h-full flex-col gap-2 rounded border border-terminal-border bg-terminal-panel p-3"
      aria-busy={!loaded && showEmpty}
    >
      <h2 className="text-sm font-semibold uppercase tracking-wide text-accent-yellow">Heatmap</h2>

      {showEmpty ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-1 py-6 text-center text-terminal-muted">
          <span className="text-sm font-semibold">No positions yet</span>
          <span className="text-xs">Buy shares to get started.</span>
        </div>
      ) : (
        <div className="min-h-0 flex-1">
          <ResponsiveContainer width="100%" height="100%">
            <Treemap
              data={nodes}
              dataKey="weight"
              isAnimationActive={false}
              content={
                <HeatmapCell selected={selected} onSelect={onSelect} />
              }
            />
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}
