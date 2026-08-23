"use client";

import { useState } from "react";

import { WatchlistPanel } from "@/components/WatchlistPanel";
import { usePriceStream } from "@/hooks/usePriceStream";

export default function Home() {
  const { prices, history, status } = usePriceStream();
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);

  return (
    <main data-testid="terminal-root" className="flex flex-1 flex-col gap-4 p-6 text-zinc-100">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">FinAlly</h1>
        <span className="text-sm text-zinc-400">Connection: {status}</span>
      </header>

      <p className="text-xs text-zinc-500">Simulated market data — not real quotes.</p>

      <WatchlistPanel
        prices={prices}
        history={history}
        selected={selectedTicker}
        onSelect={setSelectedTicker}
      />
    </main>
  );
}
