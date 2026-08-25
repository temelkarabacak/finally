"use client";

import { useEffect, useRef } from "react";

import { ChatMessageBubble } from "@/components/ChatMessageBubble";
import type { ChatMessage } from "@/hooks/useChat";

type ChatMessageListProps = {
  messages: ChatMessage[];
  historyLoaded: boolean;
  sending: boolean;
};

/**
 * Scrolls internally within the fixed-height drawer -- a long conversation
 * never grows the drawer or pushes page content (03-UI-SPEC.md Layout).
 * Auto-scrolls to the bottom whenever a new message arrives.
 *
 * While the first-open history fetch is pending, shows the loading line in
 * place of everything else. Once resolved, an empty transcript renders
 * nothing here -- the quick-prompt block (owned by ChatDrawer) fills that
 * state instead. While a send is in flight, a lightweight inline "Thinking…"
 * indicator sits at the bottom of the list, not a full message bubble.
 */
export function ChatMessageList({ messages, historyLoaded, sending }: ChatMessageListProps) {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    // jsdom does not implement scrollIntoView -- optional-chain the method
    // itself, not just the ref, so tests that mount this component don't
    // crash (the real browser always has it).
    bottomRef.current?.scrollIntoView?.({ block: "end" });
  }, [messages.length]);

  return (
    <div
      className="flex flex-1 flex-col gap-2 overflow-y-auto p-4"
      data-testid="chat-message-list"
    >
      {!historyLoaded ? (
        <p className="text-sm text-terminal-muted" data-testid="chat-history-loading">
          Loading conversation…
        </p>
      ) : (
        messages.map((message, index) => <ChatMessageBubble key={index} message={message} />)
      )}
      {sending && (
        <p className="text-sm text-terminal-muted" data-testid="chat-thinking">
          Thinking…
        </p>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
