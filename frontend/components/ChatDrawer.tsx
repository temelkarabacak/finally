"use client";

import { useEffect, useState, type FormEvent } from "react";

import { ChatMessageList } from "@/components/ChatMessageList";
import { useChat } from "@/hooks/useChat";

type ChatDrawerProps = {
  onActionsExecuted?: () => void | Promise<void>;
};

/**
 * Exactly three, fixed (D-07/D-08): one analysis prompt, one advice
 * prompt, one action prompt. Clicking a button sends its exact text
 * immediately -- it never populates the input box first.
 */
const QUICK_PROMPTS = ["Analyze my portfolio", "What should I buy?", "Add a ticker to watchlist"];

/**
 * Collapsed-by-default right-hand panel: a fixed toggle pill when closed,
 * a fixed-width sidebar sharing the flex row with <main> when open -- it
 * pushes/reflows the trading grid rather than overlaying it (user request,
 * superseding the original D-01/D-02 bottom-overlay decisions). The parent
 * page.tsx wraps <main> and this component in a flex row so the sidebar's
 * width is subtracted from <main>'s available space.
 */
export function ChatDrawer({ onActionsExecuted }: ChatDrawerProps) {
  const [open, setOpen] = useState(false);
  const { messages, draft, setDraft, sending, historyLoaded, sendMessage, loadHistory } =
    useChat(onActionsExecuted);

  useEffect(() => {
    if (open) {
      // Guarded internally by a ref in useChat -- safe to call on every
      // open, only the first call ever issues a fetch (D-03: history is
      // fetched once per page session, only after the drawer's first open).
      loadHistory();
    }
  }, [open, loadHistory]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (sending || draft.trim().length === 0) return;
    await sendMessage(draft);
  }

  async function handleQuickPrompt(prompt: string) {
    if (sending) return;
    await sendMessage(prompt);
  }

  const showQuickPrompts = historyLoaded && messages.length === 0;

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        data-testid="chat-toggle"
        className="fixed bottom-4 right-4 z-50 rounded border border-terminal-border bg-terminal-panel px-3 py-1 text-sm font-medium text-terminal-text hover:opacity-90"
      >
        AI Chat
      </button>
    );
  }

  return (
    <div
      data-testid="chat-drawer"
      className="flex h-full w-96 flex-shrink-0 flex-col border-l border-terminal-border bg-terminal-bg"
    >
      <div className="flex items-center justify-between border-b border-terminal-border p-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-accent-yellow">
          AI Chat
        </h2>
        <button
          type="button"
          onClick={() => setOpen(false)}
          data-testid="chat-toggle"
          className="rounded border border-terminal-border bg-terminal-panel px-3 py-1 text-sm font-medium text-terminal-text hover:opacity-90"
        >
          Close Chat
        </button>
      </div>

      <ChatMessageList messages={messages} historyLoaded={historyLoaded} sending={sending} />

      {showQuickPrompts && (
        <div className="border-t border-terminal-border p-3">
          <p className="mb-2 text-sm text-terminal-muted">
            Ask about your portfolio, or tell me what to trade.
          </p>
          <div className="flex flex-wrap gap-2" data-testid="chat-quick-prompts">
            {QUICK_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                type="button"
                onClick={() => handleQuickPrompt(prompt)}
                className="rounded bg-accent-purple px-3 py-1 text-sm font-medium text-terminal-text hover:opacity-90"
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      )}

      <form
        className="flex items-center gap-2 border-t border-terminal-border p-3"
        onSubmit={handleSubmit}
      >
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Ask FinAlly..."
          data-testid="chat-input"
          rows={1}
          className="max-h-24 flex-1 resize-none overflow-y-auto rounded border border-terminal-border bg-terminal-bg px-2 py-1 text-sm text-terminal-text"
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
  );
}
