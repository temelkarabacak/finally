"use client";

import { TradeConfirmationCard } from "@/components/TradeConfirmationCard";
import type { ChatMessage } from "@/hooks/useChat";

type ChatMessageBubbleProps = {
  message: ChatMessage;
};

/**
 * User and assistant bubbles share identical surface/border/text size --
 * the only differentiator is horizontal alignment (03-UI-SPEC.md Color).
 * Do not colour-code the sender: accent-blue keeps its existing
 * selection/chart-line meaning.
 *
 * The bubble text renders first; below it, one TradeConfirmationCard per
 * entry in the assistant's actions.trades, stacked with gap-2 (D-04). Zero
 * trades renders no cards. Watchlist changes get no card at all (D-06) --
 * they are narrated in the message text the bubble already renders. A user
 * message never carries actions, so it never renders a card.
 */
export function ChatMessageBubble({ message }: ChatMessageBubbleProps) {
  const isUser = message.role === "user";
  const trades = isUser ? [] : (message.actions?.trades ?? []);

  return (
    <div className={`flex flex-col gap-2 ${isUser ? "items-end" : "items-start"}`}>
      <div
        className="max-w-[80%] rounded border border-terminal-border bg-terminal-panel p-3 text-sm text-terminal-text whitespace-pre-wrap"
        data-testid={isUser ? "chat-message-user" : "chat-message-assistant"}
      >
        {message.content}
      </div>
      {trades.length > 0 && (
        <div className="flex w-full max-w-[80%] flex-col gap-2">
          {trades.map((trade, index) => (
            <TradeConfirmationCard key={index} trade={trade} />
          ))}
        </div>
      )}
    </div>
  );
}
