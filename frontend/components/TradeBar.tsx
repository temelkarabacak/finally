"use client";

import { useEffect, useState, type FormEvent } from "react";

type TradeBarProps = {
  selectedTicker: string | null;
  onTraded: () => void | Promise<void>;
};

type Side = "buy" | "sell";

/**
 * Market-order trade form: ticker + quantity + Buy/Sell. No confirmation
 * dialog -- instant fill by design (planning/PLAN.md §2, §9). Buy and Sell
 * are disabled while a request is in flight so a double-click cannot
 * produce two fills, and disabled until both fields hold a valid value so
 * an incomplete form cannot submit a malformed request.
 */
export function TradeBar({ selectedTicker, onTraded }: TradeBarProps) {
  const [ticker, setTicker] = useState("");
  const [quantity, setQuantity] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Prefill from ticker selection (D-07): clicking a watchlist/positions/
  // heatmap row readies the bar for that symbol without retyping.
  useEffect(() => {
    if (selectedTicker) setTicker(selectedTicker);
  }, [selectedTicker]);

  const parsedQuantity = Number(quantity);
  const canSubmit = ticker.trim().length > 0 && parsedQuantity > 0 && !submitting;

  async function submitTrade(side: Side, event: FormEvent) {
    event.preventDefault();
    if (!canSubmit) return;

    setSubmitting(true);
    try {
      const response = await fetch("/api/portfolio/trade", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, side, quantity: parsedQuantity }),
      });

      if (response.ok) {
        setQuantity("");
        setErrorMessage(null);
        await onTraded();
      } else if (response.status === 400) {
        const body = (await response.json()) as { detail?: string };
        setErrorMessage(body.detail ?? "Could not complete that trade — try again.");
      } else {
        setErrorMessage("Could not complete that trade — try again.");
      }
    } catch {
      setErrorMessage("Could not complete that trade — try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="flex flex-col gap-2 rounded border border-terminal-border bg-terminal-panel p-3">
      <form
        className="flex items-center gap-2"
        onSubmit={(event) => event.preventDefault()}
      >
        <input
          value={ticker}
          onChange={(event) => setTicker(event.target.value.toUpperCase())}
          placeholder="Ticker..."
          data-testid="trade-ticker-input"
          className="rounded border border-terminal-border bg-terminal-bg px-2 py-1 font-mono text-sm uppercase text-terminal-text"
        />
        <input
          type="number"
          step="any"
          min="0"
          value={quantity}
          onChange={(event) => setQuantity(event.target.value)}
          placeholder="Quantity"
          data-testid="trade-quantity-input"
          className="rounded border border-terminal-border bg-terminal-bg px-2 py-1 font-mono text-sm text-terminal-text"
        />
        <button
          type="submit"
          disabled={!canSubmit}
          onClick={(event) => submitTrade("buy", event)}
          className="rounded bg-accent-purple px-3 py-1 text-sm font-medium text-terminal-text hover:opacity-90 disabled:opacity-40"
        >
          {submitting ? "Submitting…" : "Buy"}
        </button>
        <button
          type="submit"
          disabled={!canSubmit}
          onClick={(event) => submitTrade("sell", event)}
          className="rounded bg-accent-purple px-3 py-1 text-sm font-medium text-terminal-text hover:opacity-90 disabled:opacity-40"
        >
          {submitting ? "Submitting…" : "Sell"}
        </button>
        {errorMessage && <span className="text-xs text-down">{errorMessage}</span>}
      </form>
    </section>
  );
}
