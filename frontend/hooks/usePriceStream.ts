"use client";

import { useEffect, useRef, useState } from "react";

export type PriceTick = {
  ticker: string;
  price: number;
  previous_price: number;
  timestamp: number;
  change: number;
  change_percent: number;
  direction: "up" | "down" | "flat";
};

export type ConnectionState = "connecting" | "open" | "reconnecting" | "closed";

export type ChartPoint = { time: number; value: number };

const HISTORY_LIMIT = 120;

/**
 * Subscribes to the backend's SSE price stream and accumulates per-ticker
 * history since the hook mounted. EventSource handles reconnection natively
 * (the server sends a `retry: 1000` directive) -- no custom retry logic here.
 */
export function usePriceStream(): {
  prices: Record<string, PriceTick>;
  history: Record<string, number[]>;
  timeline: Record<string, ChartPoint[]>;
  status: ConnectionState;
} {
  const [prices, setPrices] = useState<Record<string, PriceTick>>({});
  const [history, setHistory] = useState<Record<string, number[]>>({});
  const [timeline, setTimeline] = useState<Record<string, ChartPoint[]>>({});
  const [status, setStatus] = useState<ConnectionState>("connecting");
  const hasOpenedRef = useRef(false);

  useEffect(() => {
    const es = new EventSource('/api/stream/prices');

    es.addEventListener("open", () => {
      hasOpenedRef.current = true;
      setStatus("open");
    });

    es.addEventListener("error", () => {
      // A closed EventSource does not auto-retry; anything else does.
      setStatus(es.readyState === EventSource.CLOSED ? "closed" : "reconnecting");
    });

    es.addEventListener("message", (event: MessageEvent<string>) => {
      const payload = JSON.parse(event.data) as Record<string, PriceTick>;

      setPrices((prev) => ({ ...prev, ...payload }));

      setHistory((prev) => {
        const next = { ...prev };
        for (const [ticker, tick] of Object.entries(payload)) {
          const existing = next[ticker] ?? [];
          next[ticker] = [...existing, tick.price].slice(-HISTORY_LIMIT);
        }
        return next;
      });

      // Lightweight Charts requires strictly ascending, unique time values.
      // SSE frames arrive roughly every 500ms, so flooring to whole seconds
      // produces duplicate and occasionally out-of-order seconds -- dedupe
      // before appending rather than handing the library raw timestamps.
      setTimeline((prev) => {
        const next = { ...prev };
        for (const [ticker, tick] of Object.entries(payload)) {
          const existing = next[ticker] ?? [];
          const flooredTime = Math.floor(tick.timestamp);
          const last = existing[existing.length - 1];
          let updated: ChartPoint[];
          if (last && flooredTime === last.time) {
            updated = [...existing.slice(0, -1), { time: flooredTime, value: tick.price }];
          } else if (last && flooredTime < last.time) {
            updated = existing;
          } else {
            updated = [...existing, { time: flooredTime, value: tick.price }];
          }
          next[ticker] = updated.slice(-HISTORY_LIMIT);
        }
        return next;
      });
    });

    return () => {
      es.close();
    };
  }, []);

  return { prices, history, timeline, status };
}
