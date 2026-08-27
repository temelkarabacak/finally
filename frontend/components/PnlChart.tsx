'use client';

import { useEffect, useRef } from "react";
import {
  createChart,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";

import type { PnlPoint } from "@/hooks/usePortfolio";
import { formatCurrency } from "@/lib/format";

type PnlChartProps = {
  points: PnlPoint[];
  error?: string | null;
  ready: boolean;
};

/**
 * Lightweight Charts line series of total portfolio value over time,
 * mirroring PriceChart.tsx's structure almost verbatim (UI-05). Chart
 * creation touches the DOM directly, so this must be a client component
 * and cannot run during the static export's build-time prerender.
 */
export function PnlChart({ points, error, ready }: PnlChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Line"> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
      layout: {
        background: { color: "transparent" },
        textColor: "#e6edf3",
      },
      grid: {
        vertLines: { color: "#30363d" },
        horzLines: { color: "#30363d" },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: true,
        borderColor: "#30363d",
      },
      rightPriceScale: {
        borderColor: "#30363d",
      },
      localization: {
        priceFormatter: formatCurrency,
      },
    });
    const series = chart.addSeries(LineSeries, {
      color: "#209dd7",
      lineWidth: 2,
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      chart.applyOptions({ width: entry.contentRect.width, height: entry.contentRect.height });
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  // setData hands the whole array to the series at once so the line is
  // replaced rather than appended to.
  useEffect(() => {
    seriesRef.current?.setData(
      points.map((point) => ({ time: point.time as UTCTimestamp, value: point.value })),
    );
  }, [points]);

  // Until at least 2 points exist -- which also covers the not-yet-loaded
  // case, since `ready` false means zero points -- the empty state resolves
  // on its own within about a minute of app start because the recorder is
  // not gated on trading (D-04), so the copy promises time rather than
  // telling the user to go buy something.
  const showEmptyState = !ready || points.length < 2;

  return (
    <div className="flex h-full min-h-64 flex-col rounded border border-terminal-border bg-terminal-panel p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-semibold uppercase tracking-wide text-accent-yellow">
          P&L
        </span>
        {error ? <span className="text-xs text-down">{error}</span> : null}
      </div>
      <div className="relative min-h-0 flex-1">
        <div ref={containerRef} className="absolute inset-0" />
        {showEmptyState ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center text-terminal-muted">
            <span className="text-sm font-semibold">Building portfolio history</span>
            <span className="text-xs">
              Chart appears once enough data points are recorded — usually within a minute.
            </span>
          </div>
        ) : null}
      </div>
    </div>
  );
}
