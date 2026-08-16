"use client";

import { useMemo } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Panel } from "./Panel";
import { useTerminal } from "@/hooks/useTerminal";
import { clockTime, money, moneyCompact, pnlTone, signedMoney } from "@/lib/format";
import { valuePortfolio } from "@/lib/valuation";

const GAIN = "#26d07c";
const LOSS = "#f2555a";

const AXIS = { stroke: "#6b7888", fontSize: 10, fontFamily: "var(--font-plex-mono)" };

/**
 * Total portfolio value over time from `portfolio_snapshots`, with the live
 * valuation appended so the line reaches the current tick between snapshots.
 */
export function PnlChart() {
  const { history, portfolio, priceOf, lastTickAt } = useTerminal();
  const valuation = valuePortfolio(portfolio, priceOf);

  const points = useMemo(() => {
    const rows = history
      .map((snapshot) => ({ t: Date.parse(snapshot.recorded_at), v: snapshot.total_value }))
      .filter((row) => Number.isFinite(row.t));
    // The live mark extends the line past the last 30s snapshot.
    if (portfolio && lastTickAt) rows.push({ t: lastTickAt, v: valuation.totalValue });
    return rows;
  }, [history, portfolio, lastTickAt, valuation.totalValue]);

  const start = points[0]?.v ?? 0;
  const sessionPnl = points.length ? (points.at(-1)?.v ?? 0) - start : 0;

  return (
    <Panel
      label="Portfolio Value"
      meta={`${history.length} snapshots`}
      actions={
        <span className={`num text-[11px] ${pnlTone(sessionPnl)}`}>{signedMoney(sessionPnl)}</span>
      }
      bodyClassName="p-2"
    >
      {points.length < 2 ? (
        <div className="flex h-full items-center justify-center px-6 text-center text-[12px] text-ink-muted">
          Waiting for portfolio snapshots. The backend records one every 30 seconds and after
          every trade.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
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
              tickFormatter={(value: number) => moneyCompact(value)}
              width={62}
              tickLine={false}
              axisLine={false}
              tick={AXIS}
              orientation="right"
            />
            <ReferenceLine y={start} stroke="#2e3a4b" strokeDasharray="3 3" />
            <Tooltip
              cursor={{ stroke: "#2e3a4b" }}
              labelFormatter={(value) => clockTime(Number(value))}
              formatter={(value) => [money(Number(value)), "Total value"]}
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
            <Line
              type="monotone"
              dataKey="v"
              stroke={sessionPnl >= 0 ? GAIN : LOSS}
              strokeWidth={1.5}
              isAnimationActive={false}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </Panel>
  );
}
