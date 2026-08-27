"use client";

import { useCallback, useRef, useState } from "react";

export type ExecutedTrade = {
  success: boolean;
  ticker: string;
  side: string;
  quantity: number;
  price?: number;
  reason?: string;
};

export type ExecutedWatchlistChange = {
  success: boolean;
  ticker: string;
  action: string;
  reason?: string;
};

export type ChatActions = {
  trades: ExecutedTrade[];
  watchlist_changes: ExecutedWatchlistChange[];
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  actions?: ChatActions;
  errored?: boolean;
};

type HistoryEntry = {
  role: "user" | "assistant";
  content: string;
  actions: ChatActions | null;
};

/**
 * The one shared string for every degraded turn (CHAT-05/EV-2/EV-6),
 * mirroring the backend's own GENERIC_RETRY_MESSAGE constant exactly. Used
 * two ways: to construct a synthetic error message when no backend body is
 * available at all (a thrown fetch, a non-ok status), and to detect -- by
 * equality -- that a 200 response body IS the backend's own degraded reply,
 * so it can be marked `errored` for the red-bordered bubble. When the
 * backend does answer, its string is rendered verbatim either way; this
 * constant is never used to reword it client-side.
 */
export const GENERIC_RETRY_MESSAGE = "Something went wrong — please try again.";

/**
 * Message list state, draft state, and the send path for the chat drawer.
 * `sendMessage` mirrors TradeBar.tsx's submit shape exactly: guard on
 * `sending`, fetch, branch on response.ok, catch, finally. The user's
 * message is appended optimistically; `draft` is cleared only on a
 * genuinely successful (non-errored) reply (D-10) so a failed turn leaves
 * the typed text in place for a one-click resend.
 *
 * `loadHistory` GETs the persisted transcript once per page session --
 * guarded by a ref, not state, so a re-render never re-triggers the fetch
 * -- and is a no-op until the drawer's first open per 03-UI-SPEC.md's
 * "collapsed by default, chat is opt-in" philosophy.
 *
 * `onActionsExecuted` is invoked after any non-errored turn whose
 * actions.trades or actions.watchlist_changes is non-empty, so a
 * chat-executed fill can refresh the same portfolio state a manual trade
 * bar fill refreshes.
 */
export function useChat(onActionsExecuted?: () => void | Promise<void>): {
  messages: ChatMessage[];
  draft: string;
  setDraft: (value: string) => void;
  sending: boolean;
  historyLoaded: boolean;
  sendMessage: (text: string) => Promise<void>;
  loadHistory: () => Promise<void>;
} {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const historyLoadStarted = useRef(false);

  const loadHistory = useCallback(async () => {
    if (historyLoadStarted.current) return;
    historyLoadStarted.current = true;

    try {
      const response = await fetch("/api/chat/history");
      if (response.ok) {
        const body = (await response.json()) as HistoryEntry[];
        setMessages(
          body.map((entry) => ({
            role: entry.role,
            content: entry.content,
            actions: entry.actions ?? undefined,
          })),
        );
      }
    } catch {
      // Leave the transcript empty on a fetch failure -- the quick-prompt
      // starter state is a harmless fallback, not a second error UI.
    } finally {
      setHistoryLoaded(true);
    }
  }, []);

  async function sendMessage(text: string) {
    if (sending || text.trim().length === 0) return;

    setSending(true);
    setMessages((prev) => [...prev, { role: "user", content: text }]);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });

      if (response.ok) {
        const body = (await response.json()) as { message: string; actions: ChatActions };
        const errored = body.message === GENERIC_RETRY_MESSAGE;
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: body.message, actions: body.actions, errored },
        ]);

        if (!errored) {
          setDraft("");
          const hasExecutedActions =
            body.actions.trades.length > 0 || body.actions.watchlist_changes.length > 0;
          if (hasExecutedActions) {
            await onActionsExecuted?.();
          }
        }
      } else {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: GENERIC_RETRY_MESSAGE, errored: true },
        ]);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: GENERIC_RETRY_MESSAGE, errored: true },
      ]);
    } finally {
      setSending(false);
    }
  }

  return { messages, draft, setDraft, sending, historyLoaded, sendMessage, loadHistory };
}
