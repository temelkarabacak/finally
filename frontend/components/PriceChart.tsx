'use client';

import { useEffect, useRef } from "react";
import {
  createChart,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";

import type { ChartPoint } from "@/hooks/usePriceStream";

type PriceChartProps = {
  ticker: string | null;
  points: ChartPoint[];
};

/**
 * Lightweight Charts v5 wrapper for the currently-selected ticker
 * (01-CONTEXT.md: Lightweight Charts for the main per-ticker chart).
 * Chart creation touches the DOM directly, so this must be a client
 * component and cannot run during the static export's build-time prerender.
 */
export function PriceChart({ ticker, points }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Line"> | null>(null);

  // Create the chart once on mount; tear it down once on unmount so a fast
  // forward through several ticker selections cannot leak canvases.
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

  // setData replaces the series wholesale so switching tickers never
  // appends one ticker's prices onto another's. Zero or one point is a
  // valid setData call -- it renders bare axes with no line, never a
  // reason to unmount the chart.
  useEffect(() => {
    seriesRef.current?.setData(
      points.map((point) => ({ time: point.time as UTCTimestamp, value: point.value })),
    );
  }, [ticker, points]);

  return (
    <div className="flex h-full min-h-64 flex-col rounded border border-terminal-border bg-terminal-panel p-3">
      {ticker ? (
        <span className="mb-2 text-sm font-semibold text-terminal-text">{ticker}</span>
      ) : (
        <span className="mb-2 text-sm text-terminal-muted">Select a ticker to see its chart</span>
      )}
      <div ref={containerRef} className="min-h-0 flex-1" />
    </div>
  );
}
