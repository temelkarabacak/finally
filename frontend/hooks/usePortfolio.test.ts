import { describe, it, expect } from "vitest";

import { revalue, type PortfolioView } from "@/hooks/usePortfolio";
import { formatCurrency } from "@/lib/format";
import type { PriceTick } from "@/hooks/usePriceStream";

function makeTick(overrides: Partial<PriceTick> = {}): PriceTick {
  return {
    ticker: "AAPL",
    price: 200,
    previous_price: 190,
    timestamp: Date.now() / 1000,
    change: 10,
    change_percent: 5,
    direction: "up",
    ...overrides,
  };
}

function makePortfolio(overrides: Partial<PortfolioView> = {}): PortfolioView {
  return {
    cash_balance: 5000,
    holdings_value: 5000,
    total_value: 10000,
    unrealized_pnl: 0,
    positions: [
      {
        ticker: "AAPL",
        quantity: 10,
        avg_cost: 190,
        current_price: 190,
        market_value: 1900,
        unrealized_pnl: 0,
        unrealized_pnl_percent: 0,
      },
      {
        ticker: "GOOGL",
        quantity: 2.5,
        avg_cost: 150,
        current_price: 150,
        market_value: 375,
        unrealized_pnl: 0,
        unrealized_pnl_percent: 0,
      },
    ],
    ...overrides,
  };
}

describe("revalue", () => {
  it("recomputes market_value, unrealized_pnl, and unrealized_pnl_percent from a live tick", () => {
    const portfolio = makePortfolio();
    const prices: Record<string, PriceTick> = { AAPL: makeTick({ price: 200 }) };

    const result = revalue(portfolio, prices);
    const aapl = result.positions.find((p) => p.ticker === "AAPL")!;

    expect(aapl.market_value).toBeCloseTo(10 * 200, 6);
    expect(aapl.unrealized_pnl).toBeCloseTo((200 - 190) * 10, 6);
    expect(aapl.unrealized_pnl_percent).toBeCloseTo(((200 - 190) / 190) * 100, 6);
  });

  it("leaves a position untouched when no live tick exists for it", () => {
    const portfolio = makePortfolio();
    const prices: Record<string, PriceTick> = { AAPL: makeTick({ price: 200 }) };

    const result = revalue(portfolio, prices);
    const googl = result.positions.find((p) => p.ticker === "GOOGL")!;

    expect(googl).toEqual(portfolio.positions[1]);
  });

  it("never alters cash_balance, quantity, or avg_cost", () => {
    const portfolio = makePortfolio();
    const prices: Record<string, PriceTick> = { AAPL: makeTick({ price: 200 }) };

    const result = revalue(portfolio, prices);
    const aapl = result.positions.find((p) => p.ticker === "AAPL")!;

    expect(result.cash_balance).toBe(portfolio.cash_balance);
    expect(aapl.quantity).toBe(portfolio.positions[0].quantity);
    expect(aapl.avg_cost).toBe(portfolio.positions[0].avg_cost);
  });

  it("yields a P&L percent of 0 rather than Infinity or NaN when avg_cost is 0", () => {
    const portfolio = makePortfolio({
      positions: [
        {
          ticker: "AAPL",
          quantity: 10,
          avg_cost: 0,
          current_price: 0,
          market_value: 0,
          unrealized_pnl: 0,
          unrealized_pnl_percent: 0,
        },
      ],
    });
    const prices: Record<string, PriceTick> = { AAPL: makeTick({ price: 200 }) };

    const result = revalue(portfolio, prices);
    const aapl = result.positions.find((p) => p.ticker === "AAPL")!;

    expect(aapl.unrealized_pnl_percent).toBe(0);
    expect(Number.isFinite(aapl.unrealized_pnl_percent)).toBe(true);
  });

  it("produces the exact product for a fractional quantity", () => {
    const portfolio = makePortfolio();
    const prices: Record<string, PriceTick> = { GOOGL: makeTick({ ticker: "GOOGL", price: 160 }) };

    const result = revalue(portfolio, prices);
    const googl = result.positions.find((p) => p.ticker === "GOOGL")!;

    expect(googl.market_value).toBeCloseTo(2.5 * 160, 6);
    expect(formatCurrency(googl.market_value)).toBe("400.00");
  });
});

describe("formatCurrency", () => {
  it("renders to exactly two decimals with a thousands separator", () => {
    expect(formatCurrency(1234567.891)).toBe("1,234,567.89");
  });

  it("pads a whole number to two decimal places", () => {
    expect(formatCurrency(0)).toBe("0.00");
  });
});
