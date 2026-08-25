"use client";

import type { ChatMessage } from "@/hooks/useChat";

type ChatMessageBubbleProps = {
  message: ChatMessage;
};

/**
 * User and assistant bubbles share identical surface/border/text size --
 * the only differentiator is horizontal alignment (03-UI-SPEC.md Color).
 * Do not colour-code the sender: accent-blue keeps its existing
 * selection/chart-line meaning.
 */
export function ChatMessageBubble({ message }: ChatMessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className="max-w-[80%] rounded border border-terminal-border bg-terminal-panel p-3 text-sm text-terminal-text whitespace-pre-wrap"
        data-testid={isUser ? "chat-message-user" : "chat-message-assistant"}
      >
        {message.content}
      </div>
    </div>
  );
}
