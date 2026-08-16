"use client";

import { useEffect, useRef, useState } from "react";
import type { ConnectionState, PriceTick } from "@/lib/types";

export interface SeriesPoint {
  t: number;
  p: number;
}

export interface PriceStream {
  prices: Record<string, PriceTick>;
  series: Record<string, SeriesPoint[]>;
  connection: ConnectionState;
  tickCount: number;
  lastTickAt: number | null;
}

/** ~2 minutes of history at the 500ms stream cadence. */
const MAX_POINTS = 240;
const FLUSH_MS = 250;

const empty: PriceStream = {
  prices: {},
  series: {},
  connection: "disconnected",
  tickCount: 0,
  lastTickAt: null,
};

/**
 * Subscribes to the SSE price feed. Ticks are buffered and flushed on a timer so
 * a burst of per-ticker events costs one render instead of one render each.
 */
export function usePriceStream(): PriceStream {
  const [stream, setStream] = useState<PriceStream>(empty);
  const buffer = useRef<PriceTick[]>([]);

  useEffect(() => {
    const source = new EventSource("/api/stream/prices");

    source.onopen = () => setStream((s) => ({ ...s, connection: "connected" }));

    source.onerror = () =>
      setStream((s) => ({
        ...s,
        // EventSource retries on its own unless it has been closed for good.
        connection: source.readyState === EventSource.CLOSED ? "disconnected" : "reconnecting",
      }));

    source.onmessage = (event: MessageEvent<string>) => {
      const payload = JSON.parse(event.data) as PriceTick | PriceTick[];
      buffer.current.push(...(Array.isArray(payload) ? payload : [payload]));
    };

    const flush = setInterval(() => {
      const ticks = buffer.current;
      if (ticks.length === 0) return;
      buffer.current = [];

      setStream((prev) => {
        const prices = { ...prev.prices };
        const series = { ...prev.series };

        for (const tick of ticks) {
          prices[tick.ticker] = tick;
          const at = Date.parse(tick.timestamp) || Date.now();
          const next = [...(series[tick.ticker] ?? []), { t: at, p: tick.price }];
          series[tick.ticker] = next.length > MAX_POINTS ? next.slice(-MAX_POINTS) : next;
        }

        return {
          prices,
          series,
          connection: "connected",
          tickCount: prev.tickCount + ticks.length,
          lastTickAt: Date.now(),
        };
      });
    }, FLUSH_MS);

    return () => {
      clearInterval(flush);
      source.close();
    };
  }, []);

  return stream;
}
