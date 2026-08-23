"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";

import { Sparkline } from "@/components/Sparkline";
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

const DIRECTION_ARROW: Record<"up" | "down" | "flat", string> = {
  up: "▲",
  down: "▼",
  flat: "▬",
};

/**
 * Watchlist grid: dark terminal theme, per-row flash on price change,
 * sparkline, and keyboard-navigable row selection driving the main chart
 * (Plan 01-03). Add/remove/fetch logic is unchanged from Plan 01-02 --
 * mutations only resync the row set via a GET /api/watchlist refetch,
 * never tearing down the SSE EventSource.
 */
export function WatchlistPanel({ prices, history, selected, onSelect }: WatchlistPanelProps) {
  const [tickers, setTickers] = useState<string[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [flashClasses, setFlashClasses] = useState<Record<string, string>>({});
  const lastPriceRef = useRef<Record<string, number>>({});

  const refetch = useCallback(async () => {
    const response = await fetch("/api/watchlist");
    if (!response.ok) return;
    const data = (await response.json()) as WatchlistEntry[];
    setTickers(data.map((entry) => entry.ticker));
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  // Flash a row's background on genuine price change. Cleared naturally by
  // the browser via onAnimationEnd, not a timer that can drift. A row that
  // is re-triggered while still animating gets a forced reflow (class
  // cleared, then re-applied on the next paint) so the fade restarts cleanly
  // instead of silently no-opping mid-animation.
  useEffect(() => {
    for (const ticker of tickers) {
      const tick = prices[ticker];
      if (!tick) continue;
      const prevPrice = lastPriceRef.current[ticker];
      lastPriceRef.current[ticker] = tick.price;
      if (prevPrice === undefined || prevPrice === tick.price) continue;
      if (tick.direction !== "up" && tick.direction !== "down") continue;
      const cls = tick.direction === "up" ? "flash-up" : "flash-down";
      setFlashClasses((prev) => ({ ...prev, [ticker]: "" }));
      requestAnimationFrame(() => {
        setFlashClasses((prev) => ({ ...prev, [ticker]: cls }));
      });
    }
  }, [prices, tickers]);

  const clearFlash = useCallback((ticker: string) => {
    setFlashClasses((prev) => (prev[ticker] ? { ...prev, [ticker]: "" } : prev));
  }, []);

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

  function handleRowKeyDown(event: KeyboardEvent<HTMLTableRowElement>, ticker: string) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelect(ticker);
    }
  }

  // Memoized so a keystroke in the add-ticker input (which re-renders this
  // component ~10 times a second while typing) doesn't rebuild the row list
  // unless the data the rows actually depend on has changed.
  const rows = useMemo(
    () =>
      tickers.map((ticker) => {
        const tick = prices[ticker];
        const direction = tick?.direction ?? "flat";
        const isSelected = selected === ticker;
        return { ticker, tick, direction, isSelected };
      }),
    [tickers, prices, selected],
  );

  return (
    <section className="flex flex-col gap-2 rounded border border-terminal-border bg-terminal-panel p-3">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-accent-yellow">
        Watchlist
      </h2>

      <form onSubmit={handleAdd} className="flex items-center gap-2">
        <input
          value={inputValue}
          onChange={(event) => setInputValue(event.target.value.toUpperCase())}
          placeholder="Add ticker..."
          data-testid="watchlist-add-input"
          className="rounded border border-terminal-border bg-terminal-bg px-2 py-1 font-mono text-sm uppercase text-terminal-text"
        />
        <button
          type="submit"
          className="rounded bg-accent-purple px-3 py-1 text-sm font-medium text-terminal-text hover:opacity-90"
        >
          Add
        </button>
        {errorMessage && <span className="text-xs text-down">{errorMessage}</span>}
      </form>

      <table data-testid="watchlist-grid" className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-terminal-border text-terminal-muted">
            <th className="py-2 pr-4">Ticker</th>
            <th className="py-2 pr-4">Price</th>
            <th className="py-2 pr-4">Chg %</th>
            <th className="py-2 pr-4">History</th>
            <th className="py-2 pr-4" />
          </tr>
        </thead>
        <tbody>
          {rows.map(({ ticker, tick, direction, isSelected }) => {
            const flashClass = flashClasses[ticker] ?? "";
            const changePercent = tick?.change_percent;
            const sign = changePercent !== undefined && changePercent >= 0 ? "+" : "";
            const arrow = DIRECTION_ARROW[direction];
            const points = history[ticker] ?? [];
            const directionTextClass =
              direction === "up" ? "text-up" : direction === "down" ? "text-down" : "text-terminal-muted";

            return (
              <tr
                key={ticker}
                role="row"
                tabIndex={0}
                aria-selected={isSelected}
                onClick={() => onSelect(ticker)}
                onKeyDown={(event) => handleRowKeyDown(event, ticker)}
                onAnimationEnd={() => clearFlash(ticker)}
                className={`cursor-pointer border-b border-terminal-border/60 ${flashClass} ${
                  isSelected ? "border-l-2 border-l-accent-blue bg-terminal-bg/60" : ""
                }`}
              >
                <td className="py-2 pr-4 font-mono">{ticker}</td>
                <td className="py-2 pr-4 font-mono">{tick ? tick.price.toFixed(2) : "--"}</td>
                <td className={`py-2 pr-4 font-mono ${directionTextClass}`}>
                  {changePercent !== undefined ? (
                    <span>
                      {arrow} {sign}
                      {changePercent.toFixed(2)}%
                    </span>
                  ) : (
                    "--"
                  )}
                </td>
                <td className="py-2 pr-4">
                  <Sparkline points={points} />
                </td>
                <td className="py-2 pr-4 text-right">
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      handleRemove(ticker);
                    }}
                    aria-label={`Remove ${ticker}`}
                    className="text-xs text-terminal-muted hover:text-down"
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
