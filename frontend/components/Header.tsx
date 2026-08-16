"use client";

import { useFlash } from "@/hooks/useFlash";
import { useTerminal } from "@/hooks/useTerminal";
import { money, signedMoney, signedPercent } from "@/lib/format";
import { valuePortfolio } from "@/lib/valuation";
import type { ConnectionState } from "@/lib/types";

const CONNECTION: Record<ConnectionState, { label: string; color: string; live: boolean }> = {
  connected: { label: "Live", color: "bg-gain", live: true },
  reconnecting: { label: "Reconnecting", color: "bg-amber", live: true },
  disconnected: { label: "Offline", color: "bg-loss", live: false },
};

function Readout({
  label,
  value,
  sub,
  tone = "text-ink",
  flashClass = "",
  flashKey,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: string;
  flashClass?: string;
  flashKey?: number;
}) {
  return (
    <div className="flex flex-col justify-center px-4">
      <span className="panel-label text-[10px] leading-none">{label}</span>
      <span key={flashKey} className={`num mt-1 text-lg leading-none font-semibold ${tone} ${flashClass}`}>
        {value}
      </span>
      {sub ? <span className="num mt-1 text-[10px] leading-none text-ink-muted">{sub}</span> : null}
    </div>
  );
}

export function Header() {
  const { portfolio, priceOf, connection } = useTerminal();
  const valuation = valuePortfolio(portfolio, priceOf);
  const flash = useFlash(portfolio ? valuation.totalValue : null);
  const status = CONNECTION[connection];

  return (
    <header className="flex h-14 shrink-0 items-stretch border-b border-edge bg-panel-head">
      <div className="flex items-center gap-2.5 border-r border-edge px-4">
        {/* Wordmark: the tick mark doubles as the brand's only ornament. */}
        <span className="text-amber" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path
              d="M1 14L5.5 8.5L9 11.5L16.5 3"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="square"
            />
          </svg>
        </span>
        <span className="font-condensed text-[17px] font-bold tracking-[0.22em] uppercase">
          Fin<span className="text-amber">Ally</span>
        </span>
      </div>

      <div className="flex divide-x divide-edge">
        <Readout
          label="Portfolio Value"
          value={money(valuation.totalValue)}
          flashClass={flash.className}
          flashKey={flash.seq}
        />
        <Readout label="Cash" value={money(valuation.cash)} tone="text-ink-dim" />
        <Readout
          label="Unrealized P&L"
          value={signedMoney(valuation.unrealizedPnl)}
          sub={signedPercent(valuation.unrealizedPnlPercent)}
          tone={
            valuation.unrealizedPnl > 0
              ? "text-gain"
              : valuation.unrealizedPnl < 0
                ? "text-loss"
                : "text-ink-dim"
          }
        />
      </div>

      <div className="ml-auto flex items-center gap-2 border-l border-edge px-4">
        <span
          data-testid="connection-dot"
          data-state={connection}
          aria-hidden="true"
          className={`h-2 w-2 rounded-full ${status.color} ${status.live ? "pulse-dot" : ""}`}
        />
        <span className="panel-label text-[10px]" role="status">
          {status.label}
        </span>
      </div>
    </header>
  );
}
