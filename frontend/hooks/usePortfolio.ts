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
 * Fetches GET /api/portfolio once on mount and exposes a refresh callback
 * for the trade bar to call after a fill. Revalues the fetched portfolio
 * against the live SSE price map so the header and positions table move
 * with the stream instead of only after a trade.
 */
export function usePortfolio(prices: Record<string, PriceTick>): {
  portfolio: PortfolioView | null;
  error: string | null;
  loaded: boolean;
  refresh: () => Promise<void>;
} {
  const [portfolio, setPortfolio] = useState<PortfolioView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

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
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const revalued = useMemo(
    () => (portfolio ? revalue(portfolio, prices) : null),
    [portfolio, prices],
  );

  return { portfolio: revalued, error, loaded, refresh };
}
