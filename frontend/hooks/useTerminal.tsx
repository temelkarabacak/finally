"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import {
  addWatchlistTicker,
  executeTrade,
  fetchHistory,
  fetchPortfolio,
  fetchWatchlist,
  removeWatchlistTicker,
} from "@/lib/api";
import type { Portfolio, Snapshot, TradeRequest, WatchlistEntry } from "@/lib/types";
import { usePriceStream, type PriceStream } from "./usePriceStream";

interface TerminalValue extends PriceStream {
  portfolio: Portfolio | null;
  watchlist: WatchlistEntry[];
  history: Snapshot[];
  selected: string | null;
  select: (ticker: string) => void;
  /** Live price if the stream has it, otherwise the last REST value. */
  priceOf: (ticker: string) => number | null;
  refresh: () => Promise<void>;
  addTicker: (ticker: string) => Promise<void>;
  removeTicker: (ticker: string) => Promise<void>;
  trade: (request: TradeRequest) => Promise<void>;
}

const TerminalContext = createContext<TerminalValue | null>(null);

const POLL_MS = 5_000;

export function TerminalProvider({ children }: { children: React.ReactNode }) {
  const stream = usePriceStream();
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [watchlist, setWatchlist] = useState<WatchlistEntry[]>([]);
  const [history, setHistory] = useState<Snapshot[]>([]);
  const [selected, setSelected] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [nextPortfolio, nextWatchlist, nextHistory] = await Promise.all([
      fetchPortfolio(),
      fetchWatchlist(),
      fetchHistory(),
    ]);
    setPortfolio(nextPortfolio);
    setWatchlist(nextWatchlist);
    setHistory(nextHistory);
    setSelected((current) => current ?? nextWatchlist[0]?.ticker ?? null);
  }, []);

  useEffect(() => {
    // `refresh` awaits before its first setState, so nothing is set synchronously here.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh().catch(() => undefined);
    const timer = setInterval(() => void refresh().catch(() => undefined), POLL_MS);
    return () => clearInterval(timer);
  }, [refresh]);

  const priceOf = useCallback(
    (ticker: string) =>
      stream.prices[ticker]?.price ??
      watchlist.find((entry) => entry.ticker === ticker)?.price ??
      portfolio?.positions.find((p) => p.ticker === ticker)?.current_price ??
      null,
    [stream.prices, watchlist, portfolio],
  );

  const value = useMemo<TerminalValue>(
    () => ({
      ...stream,
      portfolio,
      watchlist,
      history,
      selected,
      select: setSelected,
      priceOf,
      refresh,
      addTicker: async (ticker) => {
        await addWatchlistTicker(ticker);
        await refresh();
      },
      removeTicker: async (ticker) => {
        await removeWatchlistTicker(ticker);
        setSelected((current) => (current === ticker ? null : current));
        await refresh();
      },
      trade: async (request) => {
        await executeTrade(request);
        await refresh();
      },
    }),
    [stream, portfolio, watchlist, history, selected, priceOf, refresh],
  );

  return <TerminalContext.Provider value={value}>{children}</TerminalContext.Provider>;
}

export function useTerminal(): TerminalValue {
  const value = useContext(TerminalContext);
  if (!value) throw new Error("useTerminal must be used inside TerminalProvider");
  return value;
}
