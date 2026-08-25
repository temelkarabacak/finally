import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { TradeConfirmationCard } from "@/components/TradeConfirmationCard";
import { ChatMessageBubble } from "@/components/ChatMessageBubble";
import type { ExecutedTrade, ChatMessage } from "@/hooks/useChat";

describe("TradeConfirmationCard", () => {
  it("renders a successful trade with side, quantity, ticker, and formatted price", () => {
    const trade: ExecutedTrade = {
      success: true,
      ticker: "AAPL",
      side: "buy",
      quantity: 10,
      price: 190.24,
    };

    render(<TradeConfirmationCard trade={trade} />);

    const card = screen.getByTestId("trade-card");
    expect(card.textContent).toContain("BUY");
    expect(card.textContent).toContain("10");
    expect(card.textContent).toContain("AAPL");
    expect(card.textContent).toContain("190.24");
  });

  it("preserves fractional quantity precision without rounding", () => {
    const trade: ExecutedTrade = {
      success: true,
      ticker: "GOOGL",
      side: "buy",
      quantity: 2.5,
      price: 175.0,
    };

    render(<TradeConfirmationCard trade={trade} />);

    expect(screen.getByTestId("trade-card").textContent).toContain("2.5");
  });

  it("renders a rejected trade with the REJECTED label and the reason string", () => {
    const trade: ExecutedTrade = {
      success: false,
      ticker: "TSLA",
      side: "buy",
      quantity: 10000,
      reason: "Not enough cash to buy 10000 TSLA — try a smaller quantity.",
    };

    render(<TradeConfirmationCard trade={trade} />);

    const card = screen.getByTestId("trade-card-rejected");
    expect(card.textContent).toContain("REJECTED");
    expect(card.textContent).toContain("BUY");
    expect(card.textContent).toContain("10000");
    expect(card.textContent).toContain("TSLA");
    expect(card.textContent).toContain(
      "Not enough cash to buy 10000 TSLA — try a smaller quantity.",
    );
  });
});

describe("ChatMessageBubble trade card rendering", () => {
  it("renders no cards when actions.trades is empty", () => {
    const message: ChatMessage = {
      role: "assistant",
      content: "Analyzing your portfolio.",
      actions: { trades: [], watchlist_changes: [] },
    };

    render(<ChatMessageBubble message={message} />);

    expect(screen.queryAllByTestId("trade-card")).toHaveLength(0);
    expect(screen.queryAllByTestId("trade-card-rejected")).toHaveLength(0);
  });

  it("renders exactly three stacked cards for three executed trades", () => {
    const message: ChatMessage = {
      role: "assistant",
      content: "Done.",
      actions: {
        trades: [
          { success: true, ticker: "AAPL", side: "buy", quantity: 1, price: 190 },
          { success: true, ticker: "MSFT", side: "buy", quantity: 1, price: 420 },
          { success: false, ticker: "TSLA", side: "buy", quantity: 9999, reason: "no cash" },
        ],
        watchlist_changes: [],
      },
    };

    render(<ChatMessageBubble message={message} />);

    const successCards = screen.queryAllByTestId("trade-card");
    const rejectedCards = screen.queryAllByTestId("trade-card-rejected");
    expect(successCards.length + rejectedCards.length).toBe(3);
  });

  it("never renders a card for a user message", () => {
    const message: ChatMessage = {
      role: "user",
      content: "Buy 10 AAPL",
    };

    render(<ChatMessageBubble message={message} />);

    expect(screen.queryAllByTestId("trade-card")).toHaveLength(0);
    expect(screen.queryAllByTestId("trade-card-rejected")).toHaveLength(0);
  });
});
