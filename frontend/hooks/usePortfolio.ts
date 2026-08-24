"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import type { PriceTick } from "@/hooks/usePriceStream";

export type PositionView = {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number | null;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_percent: number;
};

export type PortfolioView = {
  cash_balance: number;
  holdings_value: number;
  total_value: number;
  unrealized_pnl: number;
  positions: PositionView[];
};

export type PnlPoint = { time: number; value: number };

type RawHistoryPoint = { time: number; value: number; recorded_at: string };

/**
 * Same floor-and-dedupe guard usePriceStream applies to its timeline buffer:
 * the 30s recorder and a post-trade write can land in the same second by
 * design (the dual trigger is intentional, see 02-RESEARCH.md Pitfall 5),
 * and lightweight-charts rejects time values that are not strictly
 * ascending and unique. This collapses at the chart boundary only --
 * the underlying portfolio_snapshots rows are untouched.
 */
function collapseToChartPoints(raw: RawHistoryPoint[]): PnlPoint[] {
  const points: PnlPoint[] = [];
  for (const point of raw) {
    const flooredTime = Math.floor(point.time);
    const last = points[points.length - 1];
    if (last && flooredTime === last.time) {
      points[points.length - 1] = { time: flooredTime, value: point.value };
    } else if (last && flooredTime < last.time) {
      continue;
    } else {
      points.push({ time: flooredTime, value: point.value });
    }
  }
  return points;
}

/**
 * Pure re-marking function: for each position, if a live SSE price exists
 * use it as current_price and recompute market_value/unrealized_pnl/percent
 * with the same formulas the server uses; otherwise keep the server's
 * numbers untouched. The server stays authoritative for cash_balance,
 * quantity, and avg_cost -- the client only re-marks the live price.
 */
export function revalue(
  portfolio: PortfolioView,
  prices: Record<string, PriceTick>,
): PortfolioView {
  const positions = portfolio.positions.map((position) => {
    const tick = prices[position.ticker];
    if (!tick) return position;

    const currentPrice = tick.price;
    const marketValue = position.quantity * currentPrice;
    const unrealizedPnl = (currentPrice - position.avg_cost) * position.quantity;
    const unrealizedPnlPercent =
      position.avg_cost === 0
        ? 0
        : ((currentPrice - position.avg_cost) / position.avg_cost) * 100;

    return {
      ...position,
      current_price: currentPrice,
      market_value: marketValue,
      unrealized_pnl: unrealizedPnl,
      unrealized_pnl_percent: unrealizedPnlPercent,
    };
  });

  const holdingsValue = positions.reduce((sum, position) => sum + position.market_value, 0);
  const unrealizedPnl = positions.reduce((sum, position) => sum + position.unrealized_pnl, 0);
  const totalValue = portfolio.cash_balance + holdingsValue;

  return {
    ...portfolio,
    positions,
    holdings_value: holdingsValue,
    unrealized_pnl: unrealizedPnl,
    total_value: totalValue,
  };
}

/**
 * Fetches GET /api/portfolio and GET /api/portfolio/history once on mount
 * and exposes a refresh callback for the trade bar to call after a fill, so
 * a fill updates the header and the P&L chart in one pass. Revalues the
 * fetched portfolio against the live SSE price map so the header and
 * positions table move with the stream instead of only after a trade.
 */
export function usePortfolio(prices: Record<string, PriceTick>): {
  portfolio: PortfolioView | null;
  error: string | null;
  loaded: boolean;
  history: PnlPoint[];
  historyError: string | null;
  historyLoaded: boolean;
  refresh: () => Promise<void>;
} {
  const [portfolio, setPortfolio] = useState<PortfolioView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [history, setHistory] = useState<PnlPoint[]>([]);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [historyLoaded, setHistoryLoaded] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const response = await fetch("/api/portfolio");
      if (!response.ok) {
        setError("Could not load portfolio");
        return;
      }
      const data = (await response.json()) as PortfolioView;
      setPortfolio(data);
      setError(null);
    } catch {
      setError("Could not load portfolio");
    } finally {
      setLoaded(true);
    }

    try {
      const response = await fetch("/api/portfolio/history");
      if (!response.ok) {
        setHistoryError("Could not load portfolio history");
        return;
      }
      const data = (await response.json()) as RawHistoryPoint[];
      setHistory(collapseToChartPoints(data));
      setHistoryError(null);
    } catch {
      // Leave previously loaded points in place on a fetch failure.
      setHistoryError("Could not load portfolio history");
    } finally {
      setHistoryLoaded(true);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const revalued = useMemo(
    () => (portfolio ? revalue(portfolio, prices) : null),
    [portfolio, prices],
  );

  return { portfolio: revalued, error, loaded, history, historyError, historyLoaded, refresh };
}
