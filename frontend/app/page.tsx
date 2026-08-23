"use client";

import { usePriceStream } from "@/hooks/usePriceStream";

export default function Home() {
  const { prices, status } = usePriceStream();
  const tickers = Object.keys(prices).sort();

  return (
    <main data-testid="terminal-root" className="flex flex-1 flex-col gap-4 p-6 text-zinc-100">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">FinAlly</h1>
        <span className="text-sm text-zinc-400">Connection: {status}</span>
      </header>

      <p className="text-xs text-zinc-500">
        Simulated market data — not real quotes.
      </p>

      <table data-testid="watchlist-grid" className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-zinc-800 text-zinc-400">
            <th className="py-2 pr-4">Ticker</th>
            <th className="py-2 pr-4">Price</th>
          </tr>
        </thead>
        <tbody>
          {tickers.map((ticker) => (
            <tr key={ticker} className="border-b border-zinc-900">
              <td className="py-2 pr-4 font-mono">{ticker}</td>
              <td className="py-2 pr-4 font-mono">{prices[ticker].price.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
