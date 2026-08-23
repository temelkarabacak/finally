"use client";

import { useMemo, useState } from "react";

import { PriceChart } from "@/components/PriceChart";
import { WatchlistPanel } from "@/components/WatchlistPanel";
import { usePriceStream } from "@/hooks/usePriceStream";

export default function Home() {
  const { prices, history, timeline, status } = usePriceStream();
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);

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
        <span className="text-sm text-terminal-muted">
          Connection: {status}
          {selectedTicker && selectedPrice !== undefined
            ? ` | ${selectedTicker} ${selectedPrice.toFixed(2)}`
            : ""}
        </span>
      </header>

      <p className="text-xs text-terminal-muted">Simulated market data — not real quotes.</p>

      {/*
        Desktop-first two-column layout: watchlist on the left, main chart
        filling the rest. Structural room is left below for Phase 2's
        positions table, heatmap, P&L chart, and trade bar (planning/PLAN.md
        §10) -- not built here.
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
    </main>
  );
}
