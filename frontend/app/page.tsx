"use client";

import { useMemo, useState } from "react";

import { PnlChart } from "@/components/PnlChart";
import { PortfolioHeatmap } from "@/components/PortfolioHeatmap";
import { PositionsTable } from "@/components/PositionsTable";
import { PriceChart } from "@/components/PriceChart";
import { TradeBar } from "@/components/TradeBar";
import { WatchlistPanel } from "@/components/WatchlistPanel";
import { usePortfolio } from "@/hooks/usePortfolio";
import { usePriceStream } from "@/hooks/usePriceStream";
import { formatCurrency } from "@/lib/format";

const CONNECTION_DOT_COLOR: Record<string, string> = {
  open: "bg-up",
  connecting: "bg-accent-yellow",
  reconnecting: "bg-accent-yellow",
  closed: "bg-down",
};

export default function Home() {
  const { prices, history, timeline, status } = usePriceStream();
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const {
    portfolio,
    error: portfolioError,
    loaded: portfolioLoaded,
    history: pnlHistory,
    historyError,
    historyLoaded,
    refresh,
  } = usePortfolio(prices);

  const selectedPrice = selectedTicker ? prices[selectedTicker]?.price : undefined;
  const chartPoints = useMemo(
    () => (selectedTicker ? (timeline[selectedTicker] ?? []) : []),
    [selectedTicker, timeline],
  );

  return (
    <main
      data-testid="terminal-root"
      className="flex flex-1 flex-col gap-4 bg-terminal-bg p-6 text-terminal-text"
    >
      <header className="flex items-center justify-between border-b border-terminal-border pb-3">
        <h1 className="text-xl font-semibold text-accent-yellow">FinAlly</h1>
        <div className="flex items-center font-mono text-sm text-terminal-muted">
          <span className="border-l border-terminal-border px-3 first:border-l-0 first:pl-0">
            Total Value {portfolio ? formatCurrency(portfolio.total_value) : "--"}
          </span>
          <span className="border-l border-terminal-border px-3">
            Cash {portfolio ? formatCurrency(portfolio.cash_balance) : "--"}
          </span>
          <span className="flex items-center gap-2 border-l border-terminal-border px-3">
            <span
              className={`h-2 w-2 rounded-full ${CONNECTION_DOT_COLOR[status] ?? "bg-terminal-muted"}`}
            />
            Connection: {status}
            {selectedTicker && selectedPrice !== undefined
              ? ` | ${selectedTicker} ${selectedPrice.toFixed(2)}`
              : ""}
          </span>
        </div>
      </header>

      <p className="text-xs text-terminal-muted">Simulated market data — not real quotes.</p>

      <TradeBar selectedTicker={selectedTicker} onTraded={refresh} />

      {/*
        Desktop-first two-column layout: watchlist on the left, main chart
        filling the rest (planning/PLAN.md §10).
      */}
      <div className="grid flex-1 grid-cols-1 gap-4 lg:grid-cols-[minmax(0,420px)_1fr]">
        <WatchlistPanel
          prices={prices}
          history={history}
          selected={selectedTicker}
          onSelect={setSelectedTicker}
        />
        <PriceChart ticker={selectedTicker} points={chartPoints} />
      </div>

      {/*
        Positions table and heatmap row, per 02-UI-SPEC.md Layout &
        Composition -- same column template as the watchlist/chart grid so
        the panels line up.
      */}
      <div className="grid h-72 grid-cols-1 gap-4 lg:grid-cols-[minmax(0,420px)_1fr]">
        <PositionsTable
          positions={portfolio?.positions ?? []}
          loaded={portfolioLoaded}
          error={portfolioError}
          selected={selectedTicker}
          onSelect={setSelectedTicker}
        />
        <PortfolioHeatmap
          positions={portfolio?.positions ?? []}
          loaded={portfolioLoaded}
          selected={selectedTicker}
          onSelect={setSelectedTicker}
        />
      </div>

      {/*
        Full-width row beneath the positions/heatmap grid, per 02-UI-SPEC.md
        Layout & Composition.
      */}
      <div className="h-64">
        <PnlChart points={pnlHistory} error={historyError} ready={historyLoaded} />
      </div>
    </main>
  );
}
