"use client";

import { useState } from "react";
import { useTerminal } from "@/hooks/useTerminal";
import { money, price as formatPrice, quantity as formatQuantity } from "@/lib/format";
import type { TradeSide } from "@/lib/types";

const FIELD =
  "num h-7 rounded-xs border border-edge-strong bg-terminal px-2 text-[12px] text-ink placeholder:text-ink-muted focus:border-blue focus:outline-none";

export function TradeBar() {
  const { selected, priceOf, portfolio, trade } = useTerminal();
  const [ticker, setTicker] = useState("");
  const [qty, setQty] = useState("");
  const [pending, setPending] = useState<TradeSide | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<string | null>(null);
  const [loadedFrom, setLoadedFrom] = useState<string | null>(null);

  // Clicking a symbol elsewhere in the terminal loads it into the ticket, but
  // typing over it must stick — so this syncs on change of selection, not on every render.
  if (selected && selected !== loadedFrom) {
    setLoadedFrom(selected);
    setTicker(selected);
  }

  const symbol = ticker.trim().toUpperCase();
  const amount = Number(qty);
  const last = symbol ? priceOf(symbol) : null;
  const notional = last != null && amount > 0 ? last * amount : null;
  const held = portfolio?.positions.find((p) => p.ticker === symbol)?.quantity ?? 0;
  const ready = symbol.length > 0 && amount > 0;

  const submit = async (side: TradeSide) => {
    if (!ready) {
      setError("Enter a symbol and a positive quantity");
      return;
    }
    setError(null);
    setReceipt(null);
    setPending(side);
    try {
      await trade({ ticker: symbol, quantity: amount, side });
      setReceipt(`${side === "buy" ? "Bought" : "Sold"} ${formatQuantity(amount)} ${symbol}`);
      setQty("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Trade rejected");
    } finally {
      setPending(null);
    }
  };

  return (
    <section className="flex h-11 shrink-0 items-center gap-3 rounded-sm border border-edge bg-panel px-3">
      <h2 className="panel-label shrink-0">Ticket</h2>

      <form
        className="flex items-center gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          void submit("buy");
        }}
      >
        <input
          aria-label="Trade ticker"
          placeholder="SYMBOL"
          value={ticker}
          maxLength={8}
          onChange={(event) => setTicker(event.target.value.toUpperCase())}
          className={`${FIELD} w-24`}
        />
        <input
          aria-label="Trade quantity"
          placeholder="QTY"
          inputMode="decimal"
          value={qty}
          onChange={(event) => setQty(event.target.value)}
          className={`${FIELD} w-24 text-right`}
        />
        <button
          type="submit"
          disabled={pending !== null}
          className="h-7 rounded-xs border border-gain/60 bg-gain/15 px-4 text-[11px] font-semibold tracking-wider text-gain uppercase transition-colors hover:bg-gain/25 disabled:opacity-40"
        >
          Buy
        </button>
        <button
          type="button"
          disabled={pending !== null}
          onClick={() => void submit("sell")}
          className="h-7 rounded-xs border border-loss/60 bg-loss/15 px-4 text-[11px] font-semibold tracking-wider text-loss uppercase transition-colors hover:bg-loss/25 disabled:opacity-40"
        >
          Sell
        </button>
      </form>

      <div className="num flex items-center gap-4 border-l border-edge pl-3 text-[11px] text-ink-muted">
        <span>
          LAST <span className="text-ink-dim">{last == null ? "—" : formatPrice(last)}</span>
        </span>
        <span>
          EST <span className="text-ink-dim">{notional == null ? "—" : money(notional)}</span>
        </span>
        <span>
          HELD <span className="text-ink-dim">{formatQuantity(held)}</span>
        </span>
      </div>

      <div className="ml-auto min-w-0 truncate text-[11px]">
        {error ? (
          <span role="alert" className="text-loss">
            {error}
          </span>
        ) : receipt ? (
          <span role="status" className="text-gain">
            {receipt}
          </span>
        ) : null}
      </div>
    </section>
  );
}
