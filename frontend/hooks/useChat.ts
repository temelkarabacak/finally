"use client";

import { useState } from "react";

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
};

/**
 * Message list state, draft state, and the send path for the chat drawer.
 * `sendMessage` mirrors TradeBar.tsx's submit shape exactly: guard on
 * `sending`, fetch, branch on response.ok, catch, finally. The user's
 * message is appended optimistically; `draft` is cleared only on success
 * (D-10) so a failed turn leaves the typed text in place for a one-click
 * resend.
 */
export function useChat(): {
  messages: ChatMessage[];
  draft: string;
  setDraft: (value: string) => void;
  sending: boolean;
  sendMessage: (text: string) => Promise<void>;
} {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);

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
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: body.message, actions: body.actions },
        ]);
        setDraft("");
      } else {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: "Something went wrong — please try again." },
        ]);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Something went wrong — please try again." },
      ]);
    } finally {
      setSending(false);
    }
  }

  return { messages, draft, setDraft, sending, sendMessage };
}
