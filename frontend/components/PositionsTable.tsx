"use client";

import { Panel } from "./Panel";
import { PriceCell } from "./PriceCell";
import { useTerminal } from "@/hooks/useTerminal";
import { money, pnlTone, price as formatPrice, quantity, signedMoney, signedPercent } from "@/lib/format";
import { valuePortfolio } from "@/lib/valuation";

export function PositionsTable() {
  const { portfolio, priceOf, selected, select } = useTerminal();
  const valuation = valuePortfolio(portfolio, priceOf);

  return (
    <Panel
      label="Positions"
      meta={`${valuation.positions.length} open`}
      actions={
        <span className={`num text-[11px] ${pnlTone(valuation.unrealizedPnl)}`}>
          {signedMoney(valuation.unrealizedPnl)}
        </span>
      }
      bodyClassName="overflow-y-auto"
    >
      <table className="w-full border-collapse text-[12px]">
        <thead className="sticky top-0 z-10 bg-panel">
          <tr className="panel-label border-b border-edge text-[10px]">
            <th className="px-3 py-1.5 text-left font-semibold">Sym</th>
            <th className="py-1.5 text-right font-semibold">Qty</th>
            <th className="py-1.5 text-right font-semibold">Avg Cost</th>
            <th className="py-1.5 text-right font-semibold">Last</th>
            <th className="py-1.5 text-right font-semibold">Value</th>
            <th className="py-1.5 text-right font-semibold">P&L</th>
            <th className="px-3 py-1.5 text-right font-semibold">P&L%</th>
          </tr>
        </thead>
        <tbody>
          {valuation.positions.map((position) => (
            <tr
              key={position.ticker}
              onClick={() => select(position.ticker)}
              aria-selected={selected === position.ticker}
              className={`cursor-pointer border-b border-edge/60 transition-colors ${
                selected === position.ticker ? "bg-blue/10" : "hover:bg-panel-head"
              }`}
            >
              <td className="num px-3 py-1.5 font-semibold">{position.ticker}</td>
              <td className="num py-1.5 text-right text-ink-dim">{quantity(position.quantity)}</td>
              <td className="num py-1.5 text-right text-ink-dim">{formatPrice(position.avg_cost)}</td>
              <td className="py-1.5 text-right">
                <PriceCell value={position.current_price} />
              </td>
              <td className="num py-1.5 text-right text-ink-dim">{money(position.market_value)}</td>
              <td className={`num py-1.5 text-right ${pnlTone(position.unrealized_pnl)}`}>
                {signedMoney(position.unrealized_pnl)}
              </td>
              <td className={`num px-3 py-1.5 text-right ${pnlTone(position.unrealized_pnl)}`}>
                {signedPercent(position.pnl_percent)}
              </td>
            </tr>
          ))}
          {valuation.positions.length === 0 ? (
            <tr>
              <td colSpan={7} className="px-3 py-6 text-center text-[12px] text-ink-muted">
                No open positions. Use the trade bar to buy your first shares.
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </Panel>
  );
}
