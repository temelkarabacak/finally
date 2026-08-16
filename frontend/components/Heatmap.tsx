"use client";

import { useMemo } from "react";
import { ResponsiveContainer, Tooltip, Treemap } from "recharts";
import { Panel } from "./Panel";
import { useTerminal } from "@/hooks/useTerminal";
import { money, signedPercent } from "@/lib/format";
import { valuePortfolio } from "@/lib/valuation";

/** P&L percent at which the tile reaches full saturation. */
const FULL_SCALE = 5;

interface Tile {
  /** Recharts' Treemap data type requires an index signature. */
  [key: string]: unknown;
  ticker: string;
  size: number;
  pnl: number;
  pnlPercent: number;
  weight: number;
}

/** Diverging fill: neutral slate at breakeven, saturating toward gain or loss. */
function fillFor(pnlPercent: number): string {
  const intensity = Math.min(Math.abs(pnlPercent) / FULL_SCALE, 1);
  if (Math.abs(pnlPercent) < 0.01) return "#232b38";
  const hue = pnlPercent > 0 ? "#26d07c" : "#f2555a";
  return `color-mix(in oklab, ${hue} ${(12 + intensity * 58).toFixed(0)}%, #161c27)`;
}

interface TileProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  ticker?: string;
  pnlPercent?: number;
}

function TileContent({ x = 0, y = 0, width = 0, height = 0, ticker, pnlPercent = 0 }: TileProps) {
  if (!ticker || width <= 0 || height <= 0) return null;
  const roomy = width > 54 && height > 34;

  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        fill={fillFor(pnlPercent)}
        stroke="#11161f"
        strokeWidth={2}
      />
      {width > 34 && height > 18 ? (
        <text
          x={x + 6}
          y={y + 16}
          fill="#e6edf6"
          fontSize={11}
          fontWeight={600}
          fontFamily="var(--font-plex-mono)"
        >
          {ticker}
        </text>
      ) : null}
      {roomy ? (
        <text
          x={x + 6}
          y={y + 30}
          fill="#c3cddc"
          fontSize={10}
          fontFamily="var(--font-plex-mono)"
        >
          {signedPercent(pnlPercent)}
        </text>
      ) : null}
    </g>
  );
}

export function Heatmap() {
  const { portfolio, priceOf } = useTerminal();
  const valuation = valuePortfolio(portfolio, priceOf);

  const tiles = useMemo<Tile[]>(
    () =>
      valuation.positions
        .filter((position) => position.market_value > 0)
        .map((position) => ({
          ticker: position.ticker,
          size: position.market_value,
          pnl: position.unrealized_pnl,
          pnlPercent: position.pnl_percent,
          weight: position.weight,
        })),
    [valuation.positions],
  );

  return (
    <Panel
      label="Allocation"
      meta="size = weight · color = P&L"
      bodyClassName="p-2"
    >
      {tiles.length === 0 ? (
        <div className="flex h-full items-center justify-center px-6 text-center text-[12px] text-ink-muted">
          No positions to map. Buy shares and each holding appears here sized by weight.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <Treemap
            data={tiles}
            dataKey="size"
            isAnimationActive={false}
            content={<TileContent />}
          >
            <Tooltip
              formatter={(value, _name, item) => {
                const tile = item?.payload as Tile | undefined;
                return [
                  `${money(Number(value))} · ${signedPercent(tile?.pnlPercent ?? 0)}`,
                  tile?.ticker ?? "",
                ];
              }}
              contentStyle={{
                background: "#161c27",
                border: "1px solid #2e3a4b",
                borderRadius: 2,
                fontFamily: "var(--font-plex-mono)",
                fontSize: 11,
              }}
              itemStyle={{ color: "#e6edf6" }}
            />
          </Treemap>
        </ResponsiveContainer>
      )}
    </Panel>
  );
}
