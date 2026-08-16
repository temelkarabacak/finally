import type { Portfolio, Snapshot, WatchlistEntry } from "@/lib/types";

export const portfolio: Portfolio = {
  cash_balance: 5000,
  positions: [
    {
      ticker: "AAPL",
      quantity: 10,
      avg_cost: 100,
      current_price: 110,
      market_value: 1100,
      unrealized_pnl: 100,
      pnl_percent: 10,
    },
    {
      ticker: "TSLA",
      quantity: 4,
      avg_cost: 250,
      current_price: 200,
      market_value: 800,
      unrealized_pnl: -200,
      pnl_percent: -20,
    },
  ],
  positions_value: 1900,
  total_value: 6900,
  unrealized_pnl: -100,
};

export const watchlist: WatchlistEntry[] = [
  { ticker: "AAPL", price: 110, previous_price: 109, change_percent: 1.5 },
  { ticker: "TSLA", price: 200, previous_price: 201, change_percent: -2.25 },
];

export const history: Snapshot[] = [
  { total_value: 6800, recorded_at: "2026-08-16T10:00:00Z" },
  { total_value: 6900, recorded_at: "2026-08-16T10:00:30Z" },
];
