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

const HISTORY_LIMIT = 120;

/**
 * Subscribes to the backend's SSE price stream and accumulates per-ticker
 * history since the hook mounted. EventSource handles reconnection natively
 * (the server sends a `retry: 1000` directive) -- no custom retry logic here.
 */
export function usePriceStream(): {
  prices: Record<string, PriceTick>;
  history: Record<string, number[]>;
  status: ConnectionState;
} {
  const [prices, setPrices] = useState<Record<string, PriceTick>>({});
  const [history, setHistory] = useState<Record<string, number[]>>({});
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
    });

    return () => {
      es.close();
    };
  }, []);

  return { prices, history, status };
}
