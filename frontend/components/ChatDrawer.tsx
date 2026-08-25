"use client";

import { useState, type FormEvent } from "react";

import { ChatMessageList } from "@/components/ChatMessageList";
import { useChat } from "@/hooks/useChat";

type ChatDrawerProps = {
  onActionsExecuted?: () => void | Promise<void>;
};

/**
 * Collapsed-by-default bottom-drawer overlay (D-01/D-02/D-03): a fixed
 * toggle pill plus a fixed-height panel that slides up over the trading
 * grid without reflowing it. See 03-UI-SPEC.md Layout & Composition.
 */
export function ChatDrawer({ onActionsExecuted }: ChatDrawerProps) {
  const [open, setOpen] = useState(false);
  const { messages, draft, setDraft, sending, sendMessage } = useChat(onActionsExecuted);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (sending || draft.trim().length === 0) return;
    await sendMessage(draft);
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        data-testid="chat-toggle"
        className="fixed bottom-4 right-4 z-50 rounded border border-terminal-border bg-terminal-panel px-3 py-1 text-sm font-medium text-terminal-text hover:opacity-90"
      >
        {open ? "Close Chat" : "AI Chat"}
      </button>

      {open && (
        <div
          data-testid="chat-drawer"
          className="fixed inset-x-0 bottom-0 z-40 flex h-96 flex-col border-t border-terminal-border bg-terminal-bg"
        >
          <div className="border-b border-terminal-border p-3">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-accent-yellow">
              AI Chat
            </h2>
          </div>

          <ChatMessageList messages={messages} />

          <form
            className="flex items-center gap-2 border-t border-terminal-border p-3"
            onSubmit={handleSubmit}
          >
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Ask FinAlly..."
              data-testid="chat-input"
              className="flex-1 rounded border border-terminal-border bg-terminal-bg px-2 py-1 text-sm text-terminal-text"
            />
            <button
              type="submit"
              disabled={sending || draft.trim().length === 0}
              data-testid="chat-send"
              className="rounded bg-accent-purple px-3 py-1 text-sm font-medium text-terminal-text hover:opacity-90 disabled:opacity-40"
            >
              {sending ? "Sending…" : "Send"}
            </button>
          </form>
        </div>
      )}
    </>
  );
}
