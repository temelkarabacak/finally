"use client";

import { useEffect, useRef } from "react";

import { ChatMessageBubble } from "@/components/ChatMessageBubble";
import type { ChatMessage } from "@/hooks/useChat";

type ChatMessageListProps = {
  messages: ChatMessage[];
};

/**
 * Scrolls internally within the fixed-height drawer -- a long conversation
 * never grows the drawer or pushes page content (03-UI-SPEC.md Layout).
 * Auto-scrolls to the bottom whenever a new message arrives.
 */
export function ChatMessageList({ messages }: ChatMessageListProps) {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length]);

  return (
    <div
      className="flex flex-1 flex-col gap-2 overflow-y-auto p-4"
      data-testid="chat-message-list"
    >
      {messages.length === 0 ? (
        <p className="text-sm text-terminal-muted">
          Ask about your portfolio, or tell me what to trade.
        </p>
      ) : (
        messages.map((message, index) => (
          <ChatMessageBubble key={index} message={message} />
        ))
      )}
      <div ref={bottomRef} />
    </div>
  );
}
