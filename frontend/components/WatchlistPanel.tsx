"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";

import type { PriceTick } from "@/hooks/usePriceStream";

type WatchlistEntry = {
  ticker: string;
  price: number | null;
  previous_price: number | null;
  change: number | null;
  change_percent: number | null;
  direction: "up" | "down" | "flat" | null;
};

type WatchlistPanelProps = {
  prices: Record<string, PriceTick>;
  history: Record<string, number[]>;
  selected: string | null;
  onSelect: (ticker: string) => void;
};

/**
 * Watchlist grid with an inline add input and a per-row remove control
 * (01-CONTEXT.md: inline-no-modal edit UX). Prices continue arriving over
 * the existing SSE connection -- mutations only resync the row set via a
 * GET /api/watchlist refetch, never tearing down EventSource.
 *
 * `history` is accepted but unused here -- reserved for Plan 01-03's
 * sparkline. Flash animation and theming are also Plan 01-03's slice.
 */
export function WatchlistPanel({ prices, selected, onSelect }: WatchlistPanelProps) {
  const [tickers, setTickers] = useState<string[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    const response = await fetch("/api/watchlist");
    if (!response.ok) return;
    const data = (await response.json()) as WatchlistEntry[];
    setTickers(data.map((entry) => entry.ticker));
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  async function handleAdd(event: FormEvent) {
    event.preventDefault();
    const ticker = inputValue.trim().toUpperCase();
    if (!ticker) return;

    const response = await fetch("/api/watchlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker }),
    });

    if (response.status === 201) {
      setInputValue("");
      setErrorMessage(null);
      await refetch();
    } else if (response.status === 409) {
      setErrorMessage(`${ticker} is already on the watchlist`);
    } else {
      setErrorMessage(`Could not add ${ticker}`);
    }
  }

  async function handleRemove(ticker: string) {
    const response = await fetch(`/api/watchlist/${ticker}`, { method: "DELETE" });

    if (response.status === 204) {
      setErrorMessage(null);
      await refetch();
    } else if (response.status === 404) {
      setErrorMessage(`${ticker} is not on the watchlist`);
      await refetch();
    } else {
      setErrorMessage(`Could not remove ${ticker}`);
    }
  }

  return (
    <section className="flex flex-col gap-2">
      <form onSubmit={handleAdd} className="flex items-center gap-2">
        <input
          value={inputValue}
          onChange={(event) => setInputValue(event.target.value.toUpperCase())}
          placeholder="Add ticker..."
          data-testid="watchlist-add-input"
          className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 font-mono text-sm uppercase text-zinc-100"
        />
        {errorMessage && <span className="text-xs text-red-400">{errorMessage}</span>}
      </form>

      <table data-testid="watchlist-grid" className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-zinc-800 text-zinc-400">
            <th className="py-2 pr-4">Ticker</th>
            <th className="py-2 pr-4">Price</th>
            <th className="py-2 pr-4" />
          </tr>
        </thead>
        <tbody>
          {tickers.map((ticker) => {
            const tick = prices[ticker];
            return (
              <tr
                key={ticker}
                onClick={() => onSelect(ticker)}
                className={`cursor-pointer border-b border-zinc-900 ${
                  selected === ticker ? "bg-zinc-800" : ""
                }`}
              >
                <td className="py-2 pr-4 font-mono">{ticker}</td>
                <td className="py-2 pr-4 font-mono">{tick ? tick.price.toFixed(2) : "--"}</td>
                <td className="py-2 pr-4 text-right">
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      handleRemove(ticker);
                    }}
                    aria-label={`Remove ${ticker}`}
                    className="text-xs text-zinc-500 hover:text-red-400"
                  >
                    x
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
