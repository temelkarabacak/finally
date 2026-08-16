"use client";

import { useEffect, useRef, useState } from "react";
import { Panel } from "./Panel";
import { useTerminal } from "@/hooks/useTerminal";
import { fetchChatHistory, sendChat } from "@/lib/api";
import { price as formatPrice, quantity as formatQuantity } from "@/lib/format";
import type { ChatMessage, ExecutedTrade, WatchlistChange } from "@/lib/types";

const RETRY_MESSAGE = "Sorry, I could not complete that request. Please try again.";

let seq = 0;
const nextId = () => `local-${(seq += 1)}`;

function ActionChip({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  return (
    <span
      className={`num inline-flex items-center gap-1 rounded-xs border px-1.5 py-0.5 text-[10px] ${
        ok ? "border-gain/50 bg-gain/10 text-gain" : "border-loss/50 bg-loss/10 text-loss"
      }`}
    >
      {children}
    </span>
  );
}

function tradeLabel(trade: ExecutedTrade) {
  const head = `${trade.side.toUpperCase()} ${formatQuantity(trade.quantity)} ${trade.ticker}`;
  return trade.price != null ? `${head} @ ${formatPrice(trade.price)}` : head;
}

function Actions({
  trades = [],
  changes = [],
}: {
  trades?: ExecutedTrade[];
  changes?: WatchlistChange[];
}) {
  if (trades.length === 0 && changes.length === 0) return null;

  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {trades.map((trade, index) => (
        <ActionChip key={`t${index}`} ok={trade.status !== "rejected"}>
          {tradeLabel(trade)}
        </ActionChip>
      ))}
      {changes.map((change, index) => (
        <ActionChip key={`w${index}`} ok={change.status !== "rejected"}>
          {change.action === "add" ? "+" : "−"} {change.ticker}
        </ActionChip>
      ))}
    </div>
  );
}

function Bubble({ message }: { message: ChatMessage }) {
  const mine = message.role === "user";

  return (
    <li
      data-testid="chat-bubble"
      className={`flex flex-col ${mine ? "items-end" : "items-start"}`}
    >
      <span className="panel-label mb-1 text-[9px]">{mine ? "You" : "FinAlly"}</span>
      <div
        className={`max-w-[92%] rounded-sm border px-2.5 py-1.5 text-[12px] leading-relaxed whitespace-pre-wrap ${
          mine
            ? "border-violet/50 bg-violet/15 text-ink"
            : message.failed
              ? "border-loss/40 bg-loss/10 text-ink"
              : "border-edge bg-panel-head text-ink"
        }`}
      >
        {message.content}
        <Actions trades={message.trades} changes={message.watchlist_changes} />
      </div>
    </li>
  );
}

export function ChatPanel({ onCollapse }: { onCollapse: () => void }) {
  const { refresh } = useTerminal();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const logRef = useRef<HTMLUListElement>(null);

  /*
   * Sending is blocked until this settles. The stored history replaces the whole
   * message list, so a message sent while it is still in flight would be silently
   * discarded when it lands. A failed fetch still unblocks the panel.
   */
  useEffect(() => {
    fetchChatHistory()
      .then(setMessages)
      .catch(() => undefined)
      .finally(() => setHistoryLoaded(true));
  }, []);

  useEffect(() => {
    const log = logRef.current;
    if (log) log.scrollTop = log.scrollHeight;
  }, [messages, busy]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const text = draft.trim();
    if (!text || busy || !historyLoaded) return;

    setMessages((prev) => [...prev, { id: nextId(), role: "user", content: text }]);
    setDraft("");
    setBusy(true);

    try {
      const reply = await sendChat(text);
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: "assistant",
          content: reply.message,
          trades: reply.trades,
          watchlist_changes: reply.watchlist_changes,
        },
      ]);
      // Trades and watchlist edits happen server-side, so pull the new state.
      await refresh().catch(() => undefined);
    } catch {
      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: "assistant", content: RETRY_MESSAGE, failed: true },
      ]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel
      label="AI Copilot"
      meta={busy ? "thinking" : `${messages.length} messages`}
      actions={
        <button
          type="button"
          aria-label="Collapse chat"
          onClick={onCollapse}
          className="rounded-xs px-1.5 text-[11px] text-ink-muted transition-colors hover:text-ink"
        >
          ›
        </button>
      }
      className="min-w-0"
    >
      <div className="flex h-full min-h-0 flex-col">
        <ul
          ref={logRef}
          data-testid="chat-log"
          className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-3 py-3"
        >
          {historyLoaded && messages.length === 0 && !busy ? (
            <li className="text-[12px] leading-relaxed text-ink-muted">
              Ask about your positions, risk concentration, or P&L — or just say
              <span className="num text-ink-dim"> &quot;buy 5 AAPL&quot;</span> and I will execute
              it.
            </li>
          ) : null}

          {messages.map((message) => (
            <Bubble key={message.id} message={message} />
          ))}

          {busy ? (
            <li role="status" className="flex items-center gap-2 text-[11px] text-ink-muted">
              <span className="h-1.5 w-1.5 rounded-full bg-amber pulse-dot" aria-hidden="true" />
              FinAlly is thinking…
            </li>
          ) : null}
        </ul>

        <form onSubmit={submit} className="flex shrink-0 items-center gap-2 border-t border-edge p-2">
          <input
            aria-label="Message FinAlly"
            placeholder={historyLoaded ? "Ask FinAlly…" : "Loading conversation…"}
            value={draft}
            disabled={busy || !historyLoaded}
            onChange={(event) => setDraft(event.target.value)}
            className="h-8 min-w-0 flex-1 rounded-xs border border-edge-strong bg-terminal px-2 text-[12px] text-ink placeholder:text-ink-muted focus:border-blue focus:outline-none disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={busy || !historyLoaded || draft.trim().length === 0}
            className="h-8 rounded-xs bg-violet px-3 text-[11px] font-semibold tracking-wider text-ink uppercase transition-opacity hover:opacity-90 disabled:opacity-40"
          >
            Send
          </button>
        </form>
      </div>
    </Panel>
  );
}
