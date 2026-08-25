"use client";

import type { ExecutedTrade } from "@/hooks/useChat";
import { formatCurrency } from "@/lib/format";

type TradeConfirmationCardProps = {
  trade: ExecutedTrade;
};

/**
 * One executed (or rejected) trade, rendered inline beneath the assistant's
 * message bubble -- a distinct block, never merged into the bubble's own
 * text (D-04). The 4px left border is deliberately thicker than the
 * drawer's 1px borders elsewhere so the card reads as a distinct object.
 * Fractional quantities render at their real precision -- never rounded.
 * The rejected variant's reason is execute_trade()'s own rejection string,
 * rendered as-is (D-05) -- no second error vocabulary for the chat path.
 */
export function TradeConfirmationCard({ trade }: TradeConfirmationCardProps) {
  const side = trade.side.toUpperCase();

  if (!trade.success) {
    return (
      <div
        data-testid="trade-card-rejected"
        className="rounded border-l-4 border-l-down bg-terminal-panel p-3 font-mono text-sm"
      >
        <p className="text-xs font-semibold uppercase text-down">REJECTED</p>
        <p>
          {side} {trade.quantity} <span className="font-semibold">{trade.ticker}</span>
        </p>
        <p className="whitespace-pre-wrap text-terminal-muted">{trade.reason}</p>
      </div>
    );
  }

  const priceText = trade.price !== undefined ? formatCurrency(trade.price) : "";

  return (
    <div
      data-testid="trade-card"
      className="rounded border-l-4 border-l-up bg-terminal-panel p-3 font-mono text-sm"
    >
      {side} {trade.quantity} <span className="font-semibold">{trade.ticker}</span> @ $
      {priceText}
    </div>
  );
}
