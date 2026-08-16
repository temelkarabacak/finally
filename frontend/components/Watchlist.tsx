"use client";

import { useState } from "react";
import { Panel } from "./Panel";
import { PriceCell } from "./PriceCell";
import { Sparkline } from "./Sparkline";
import { useTerminal } from "@/hooks/useTerminal";
import { signedPercent } from "@/lib/format";
import type { WatchlistEntry } from "@/lib/types";

const GAIN = "#26d07c";
const LOSS = "#f2555a";
const FLAT = "#6b7888";

function changePercent(entry: WatchlistEntry, tickPrevious?: number, live?: number | null) {
  if (entry.change_percent != null) return entry.change_percent;
  if (live != null && tickPrevious) return ((live - tickPrevious) / tickPrevious) * 100;
  return null;
}

export function Watchlist() {
  const { watchlist, prices, series, selected, select, addTicker, removeTicker, priceOf } =
    useTerminal();
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const ticker = draft.trim().toUpperCase();
    if (!ticker) return;
    setError(null);
    try {
      await addTicker(ticker);
      setDraft("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not add ticker");
    }
  };

  return (
    <Panel
      label="Watchlist"
      meta={watchlist.length}
      actions={
        <form onSubmit={submit} className="flex items-center gap-1">
          <input
            aria-label="Add ticker"
            placeholder="SYM"
            value={draft}
            maxLength={8}
            onChange={(event) => setDraft(event.target.value.toUpperCase())}
            className="num h-6 w-[68px] rounded-xs border border-edge-strong bg-terminal px-1.5 text-[11px] text-ink placeholder:text-ink-muted focus:border-blue focus:outline-none"
          />
          <button
            type="submit"
            aria-label="Add"
            className="h-6 w-6 rounded-xs border border-edge-strong text-[13px] leading-none text-ink-dim transition-colors hover:border-blue hover:text-blue"
          >
            +
          </button>
        </form>
      }
      bodyClassName="overflow-y-auto"
    >
      {error ? (
        <p role="alert" className="border-b border-edge px-3 py-1.5 text-[11px] text-loss">
          {error}
        </p>
      ) : null}

      <table className="w-full border-collapse text-[12px]">
        <thead className="sticky top-0 z-10 bg-panel">
          <tr className="panel-label border-b border-edge text-[10px]">
            <th className="px-3 py-1.5 text-left font-semibold">Sym</th>
            <th className="py-1.5 text-left font-semibold">Trend</th>
            <th className="py-1.5 text-right font-semibold">Last</th>
            <th className="px-3 py-1.5 text-right font-semibold">Chg%</th>
            <th className="w-6" />
          </tr>
        </thead>
        <tbody>
          {watchlist.map((entry) => {
            const tick = prices[entry.ticker];
            const live = priceOf(entry.ticker);
            const change = changePercent(entry, tick?.previous_price, live);
            const tone = change == null ? FLAT : change > 0 ? GAIN : change < 0 ? LOSS : FLAT;
            const isSelected = selected === entry.ticker;

            return (
              <tr
                key={entry.ticker}
                onClick={() => select(entry.ticker)}
                aria-selected={isSelected}
                className={`group cursor-pointer border-b border-edge/60 transition-colors ${
                  isSelected ? "bg-blue/10" : "hover:bg-panel-head"
                }`}
              >
                <td className="px-3 py-1.5">
                  <span
                    className={`num font-semibold ${isSelected ? "text-amber" : "text-ink"}`}
                  >
                    {entry.ticker}
                  </span>
                </td>
                <td className="py-1">
                  <Sparkline points={series[entry.ticker] ?? []} color={tone} />
                </td>
                <td className="py-1.5 text-right">
                  <PriceCell value={live} />
                </td>
                <td
                  className="num px-3 py-1.5 text-right"
                  style={{ color: tone }}
                >
                  {change == null ? "—" : signedPercent(change)}
                </td>
                <td className="pr-2">
                  <button
                    type="button"
                    aria-label={`Remove ${entry.ticker}`}
                    onClick={(event) => {
                      event.stopPropagation();
                      void removeTicker(entry.ticker);
                    }}
                    className="rounded-xs px-1 text-ink-muted opacity-0 transition-opacity group-hover:opacity-100 hover:text-loss focus-visible:opacity-100"
                  >
                    ×
                  </button>
                </td>
              </tr>
            );
          })}
          {watchlist.length === 0 ? (
            <tr>
              <td colSpan={5} className="px-3 py-6 text-center text-[12px] text-ink-muted">
                No symbols tracked. Add one above to start streaming prices.
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </Panel>
  );
}
