"use client";

import { useTerminal } from "@/hooks/useTerminal";
import { clockTime, price as formatPrice } from "@/lib/format";

/**
 * Terminal status rail: session telemetry on the left, a live tape of the most
 * recent ticks on the right. Confirms at a glance that data is actually moving.
 */
export function StatusBar() {
  const { connection, tickCount, lastTickAt, prices, watchlist } = useTerminal();

  const tape = Object.values(prices)
    .sort((a, b) => Date.parse(b.timestamp) - Date.parse(a.timestamp))
    .slice(0, 8);

  return (
    <footer className="flex h-6 shrink-0 items-center gap-4 border-t border-edge bg-panel-head px-3 text-[10px] text-ink-muted">
      <span className="panel-label text-[10px]">
        Feed <span className="text-ink-dim">{connection}</span>
      </span>
      <span className="num">
        TICKS <span className="text-ink-dim">{tickCount.toLocaleString("en-US")}</span>
      </span>
      <span className="num">
        LAST <span className="text-ink-dim">{lastTickAt ? clockTime(lastTickAt) : "--:--:--"}</span>
      </span>
      <span className="num">
        SYMBOLS <span className="text-ink-dim">{watchlist.length}</span>
      </span>

      <div className="ml-auto flex min-w-0 items-center gap-3 overflow-hidden">
        {tape.map((tick) => (
          <span key={tick.ticker} className="num shrink-0">
            <span className="text-ink-dim">{tick.ticker}</span>{" "}
            <span className={tick.direction === "up" ? "text-gain" : tick.direction === "down" ? "text-loss" : ""}>
              {tick.direction === "up" ? "▲" : tick.direction === "down" ? "▼" : "•"}
              {formatPrice(tick.price)}
            </span>
          </span>
        ))}
      </div>
    </footer>
  );
}
