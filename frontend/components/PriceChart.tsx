"use client";

import { useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Panel } from "./Panel";
import { PriceCell } from "./PriceCell";
import { useTerminal } from "@/hooks/useTerminal";
import { clockTime, price as formatPrice, signedPercent } from "@/lib/format";

const GAIN = "#26d07c";
const LOSS = "#f2555a";

const AXIS = { stroke: "#6b7888", fontSize: 10, fontFamily: "var(--font-plex-mono)" };

/** Chart of the selected symbol, accumulated from the SSE feed since page load. */
export function PriceChart() {
  const { selected, series, priceOf } = useTerminal();
  const points = useMemo(() => (selected ? (series[selected] ?? []) : []), [selected, series]);

  const { open, last, changePercent, rising } = useMemo(() => {
    const first = points[0]?.p ?? null;
    const latest = points.at(-1)?.p ?? null;
    const pct = first && latest ? ((latest - first) / first) * 100 : 0;
    return { open: first, last: latest, changePercent: pct, rising: pct >= 0 };
  }, [points]);

  const livePrice = selected ? priceOf(selected) : null;
  const tone = rising ? GAIN : LOSS;

  return (
    <Panel
      label={selected ?? "Chart"}
      meta={points.length ? `${points.length} ticks` : "awaiting feed"}
      actions={
        <div className="flex items-center gap-3">
          <PriceCell value={livePrice} className="text-[13px] font-semibold" />
          {last != null ? (
            <span className="num text-[11px]" style={{ color: tone }}>
              {signedPercent(changePercent)}
            </span>
          ) : null}
        </div>
      }
      bodyClassName="p-2"
    >
      {points.length < 2 ? (
        <div className="flex h-full items-center justify-center px-6 text-center text-[12px] text-ink-muted">
          {selected
            ? `Collecting ticks for ${selected}. The chart draws from the live feed, so it fills in as prices stream.`
            : "Select a symbol in the watchlist to chart it."}
        </div>
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="price-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={tone} stopOpacity={0.28} />
                <stop offset="100%" stopColor={tone} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#232b38" vertical={false} />
            <XAxis
              dataKey="t"
              type="number"
              domain={["dataMin", "dataMax"]}
              tickFormatter={(value: number) => clockTime(value)}
              minTickGap={48}
              tickLine={false}
              axisLine={{ stroke: "#232b38" }}
              tick={AXIS}
            />
            <YAxis
              domain={["dataMin", "dataMax"]}
              tickFormatter={(value: number) => formatPrice(value)}
              width={58}
              tickLine={false}
              axisLine={false}
              tick={AXIS}
              orientation="right"
            />
            {open != null ? (
              <ReferenceLine y={open} stroke="#2e3a4b" strokeDasharray="3 3" />
            ) : null}
            <Tooltip
              cursor={{ stroke: "#2e3a4b" }}
              labelFormatter={(value) => clockTime(Number(value))}
              formatter={(value) => [formatPrice(Number(value)), "Price"]}
              contentStyle={{
                background: "#161c27",
                border: "1px solid #2e3a4b",
                borderRadius: 2,
                fontFamily: "var(--font-plex-mono)",
                fontSize: 11,
              }}
              labelStyle={{ color: "#9aa7b8" }}
              itemStyle={{ color: "#e6edf6" }}
            />
            <Area
              type="linear"
              dataKey="p"
              stroke={tone}
              strokeWidth={1.5}
              fill="url(#price-fill)"
              isAnimationActive={false}
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </Panel>
  );
}
