"use client";

import { useMemo, type KeyboardEvent } from "react";

import type { PositionView } from "@/hooks/usePortfolio";

type PositionsTableProps = {
  positions: PositionView[];
  loaded: boolean;
  error: string | null;
  selected: string | null;
  onSelect: (ticker: string) => void;
};

const DIRECTION_ARROW: Record<"up" | "down" | "flat", string> = {
  up: "▲",
  down: "▼",
  flat: "▬",
};

function directionOf(value: number): "up" | "down" | "flat" {
  if (value > 0) return "up";
  if (value < 0) return "down";
  return "flat";
}

function directionTextClass(direction: "up" | "down" | "flat"): string {
  return direction === "up" ? "text-up" : direction === "down" ? "text-down" : "text-terminal-muted";
}

function signOf(value: number): string {
  return value >= 0 ? "+" : "";
}

function formatQuantity(quantity: number): string {
  return Number(quantity).toString();
}

/**
 * Positions grid mirroring WatchlistPanel's chrome, row selection, and
 * keyboard handling (02-PATTERNS.md). Presentational only -- page.tsx owns
 * the fetch through usePortfolio, and positions arrive already revalued
 * against the live price map, so this file does no P&L arithmetic itself.
 */
export function PositionsTable({
  positions,
  loaded,
  error,
  selected,
  onSelect,
}: PositionsTableProps) {
  function handleRowKeyDown(event: KeyboardEvent<HTMLTableRowElement>, ticker: string) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelect(ticker);
    }
  }

  const rows = useMemo(
    () =>
      positions.map((position) => ({
        ...position,
        isSelected: selected === position.ticker,
      })),
    [positions, selected],
  );

  const showEmpty = !error && positions.length === 0;

  return (
    <section
      className="flex flex-col gap-2 rounded border border-terminal-border bg-terminal-panel p-3"
      aria-busy={!loaded && showEmpty}
    >
      <h2 className="text-sm font-semibold uppercase tracking-wide text-accent-yellow">
        Positions
      </h2>

      {error ? (
        <div className="flex flex-1 items-center justify-center py-6 text-center text-xs text-down">
          {error}
        </div>
      ) : showEmpty ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-1 py-6 text-center text-terminal-muted">
          <span className="text-sm font-semibold">No positions yet</span>
          <span className="text-xs">Buy shares to get started.</span>
        </div>
      ) : (
        <div className="max-h-64 overflow-y-auto">
          <table data-testid="positions-grid" className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-terminal-border text-terminal-muted">
                <th className="py-2 pr-4">Ticker</th>
                <th className="py-2 pr-4">Qty</th>
                <th className="py-2 pr-4">Avg Cost</th>
                <th className="py-2 pr-4">Price</th>
                <th className="py-2 pr-4">P&L</th>
                <th className="py-2 pr-4">Chg %</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(
                ({
                  ticker,
                  quantity,
                  avg_cost,
                  current_price,
                  unrealized_pnl,
                  unrealized_pnl_percent,
                  isSelected,
                }) => {
                  const pnlDirection = directionOf(unrealized_pnl);
                  const pctDirection = directionOf(unrealized_pnl_percent);

                  return (
                    <tr
                      key={ticker}
                      role="row"
                      tabIndex={0}
                      aria-selected={isSelected}
                      onClick={() => onSelect(ticker)}
                      onKeyDown={(event) => handleRowKeyDown(event, ticker)}
                      className={`cursor-pointer border-b border-terminal-border/60 ${
                        isSelected ? "border-l-2 border-l-accent-blue bg-terminal-bg/60" : ""
                      }`}
                    >
                      <td className="py-2 pr-4 font-mono">{ticker}</td>
                      <td className="py-2 pr-4 font-mono">{formatQuantity(quantity)}</td>
                      <td className="py-2 pr-4 font-mono">{avg_cost.toFixed(2)}</td>
                      <td className="py-2 pr-4 font-mono">
                        {current_price !== null ? current_price.toFixed(2) : "--"}
                      </td>
                      <td className={`py-2 pr-4 font-mono ${directionTextClass(pnlDirection)}`}>
                        {DIRECTION_ARROW[pnlDirection]} {signOf(unrealized_pnl)}
                        {unrealized_pnl.toFixed(2)}
                      </td>
                      <td className={`py-2 pr-4 font-mono ${directionTextClass(pctDirection)}`}>
                        {DIRECTION_ARROW[pctDirection]} {signOf(unrealized_pnl_percent)}
                        {unrealized_pnl_percent.toFixed(2)}%
                      </td>
                    </tr>
                  );
                },
              )}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
