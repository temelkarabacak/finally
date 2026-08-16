import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ChatPanel } from "@/components/ChatPanel";
import { TerminalProvider } from "@/hooks/useTerminal";
import type { ChatMessage } from "@/lib/types";
import * as fixtures from "./fixtures";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    fetchPortfolio: vi.fn(),
    fetchWatchlist: vi.fn(),
    fetchHistory: vi.fn(),
    fetchChatHistory: vi.fn(),
    addWatchlistTicker: vi.fn(),
    removeWatchlistTicker: vi.fn(),
    executeTrade: vi.fn(),
    sendChat: vi.fn(),
  };
});

const api = vi.mocked(await import("@/lib/api"));

const renderChat = () =>
  render(<ChatPanel onCollapse={vi.fn()} />, { wrapper: TerminalProvider });

/** Renders and waits out the history fetch, which is what unblocks the input. */
async function openChat() {
  renderChat();
  const input = screen.getByLabelText("Message FinAlly");
  await waitFor(() => expect(input).toBeEnabled());
  return input;
}

beforeEach(() => {
  vi.clearAllMocks();
  api.fetchPortfolio.mockResolvedValue(fixtures.portfolio);
  api.fetchWatchlist.mockResolvedValue(fixtures.watchlist);
  api.fetchHistory.mockResolvedValue(fixtures.history);
  api.fetchChatHistory.mockResolvedValue([]);
});

describe("ChatPanel", () => {
  it("rehydrates stored conversation history", async () => {
    api.fetchChatHistory.mockResolvedValue([
      { id: "1", role: "user", content: "how am I doing?" },
      { id: "2", role: "assistant", content: "Down $100 on the day." },
    ]);
    renderChat();

    expect(await screen.findByText("how am I doing?")).toBeInTheDocument();
    expect(screen.getByText("Down $100 on the day.")).toBeInTheDocument();
  });

  it("shows the loading indicator while the model is thinking, then the reply", async () => {
    const user = userEvent.setup();
    let resolve!: (value: { message: string }) => void;
    api.sendChat.mockReturnValue(new Promise((r) => (resolve = r)));
    const input = await openChat();

    await user.type(input, "buy 5 AAPL");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(screen.getByText("buy 5 AAPL")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("FinAlly is thinking");
    expect(screen.getByLabelText("Message FinAlly")).toBeDisabled();

    resolve({ message: "Order filled." });

    expect(await screen.findByText("Order filled.")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());
  });

  it("renders executed trades and watchlist changes as inline chips", async () => {
    const user = userEvent.setup();
    api.sendChat.mockResolvedValue({
      message: "Done.",
      trades: [{ ticker: "AAPL", side: "buy", quantity: 5, price: 110, status: "executed" }],
      watchlist_changes: [{ ticker: "PYPL", action: "add", status: "executed" }],
    });
    const input = await openChat();

    await user.type(input, "buy 5 AAPL and watch PYPL");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("BUY 5 AAPL @ 110.00")).toBeInTheDocument();
    expect(screen.getByText("+ PYPL")).toBeInTheDocument();
  });

  it("marks a rejected trade chip in the loss tone", async () => {
    const user = userEvent.setup();
    api.sendChat.mockResolvedValue({
      message: "Not completed: insufficient cash",
      trades: [
        {
          ticker: "NVDA",
          side: "buy",
          quantity: 100,
          status: "rejected",
          error: "insufficient cash",
        },
      ],
    });
    const input = await openChat();

    await user.type(input, "buy 100 NVDA");
    await user.click(screen.getByRole("button", { name: "Send" }));

    const chip = await screen.findByText("BUY 100 NVDA");
    expect(chip.className).toContain("text-loss");
  });

  it("shows the generic retry message when the request times out", async () => {
    const user = userEvent.setup();
    api.sendChat.mockRejectedValue(new DOMException("timed out", "TimeoutError"));
    const input = await openChat();

    await user.type(input, "analyse my risk");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(
      await screen.findByText(/could not complete that request. Please try again/),
    ).toBeInTheDocument();
  });

  it("refreshes portfolio state after the assistant acts", async () => {
    const user = userEvent.setup();
    api.sendChat.mockResolvedValue({ message: "Bought." });
    const input = await openChat();
    await waitFor(() => expect(api.fetchPortfolio).toHaveBeenCalled());
    const before = api.fetchPortfolio.mock.calls.length;

    await user.type(input, "buy 1 AAPL");
    await user.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() =>
      expect(api.fetchPortfolio.mock.calls.length).toBeGreaterThan(before),
    );
  });

  describe("history load race", () => {
    it("blocks sending until the stored history has settled", async () => {
      let resolveHistory!: (value: ChatMessage[]) => void;
      api.fetchChatHistory.mockReturnValue(new Promise((r) => (resolveHistory = r)));
      renderChat();

      const input = screen.getByLabelText("Message FinAlly");
      expect(input).toBeDisabled();
      expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();

      resolveHistory([{ id: "h1", role: "user", content: "earlier question" }]);

      await waitFor(() => expect(input).toBeEnabled());
      expect(await screen.findByText("earlier question")).toBeInTheDocument();
    });

    it("unblocks the panel even when the history fetch fails", async () => {
      api.fetchChatHistory.mockRejectedValue(new Error("offline"));
      renderChat();

      await waitFor(() => expect(screen.getByLabelText("Message FinAlly")).toBeEnabled());
    });

    it("never discards a sent exchange when history lands first", async () => {
      const user = userEvent.setup();
      let resolveHistory!: (value: ChatMessage[]) => void;
      api.fetchChatHistory.mockReturnValue(new Promise((r) => (resolveHistory = r)));
      api.sendChat.mockResolvedValue({ message: "Up 2% today." });
      renderChat();

      // The clobber window: try to send while history is still in flight. Before the
      // gate this went through, and the late history then replaced the whole list.
      await user.type(screen.getByLabelText("Message FinAlly"), "how am I doing?");
      await user.click(screen.getByRole("button", { name: "Send" }));
      expect(api.sendChat).not.toHaveBeenCalled();
      expect(screen.queryAllByTestId("chat-bubble")).toHaveLength(0);

      resolveHistory([{ id: "h1", role: "assistant", content: "stored greeting" }]);
      await waitFor(() => expect(screen.getByLabelText("Message FinAlly")).toBeEnabled());

      await user.type(screen.getByLabelText("Message FinAlly"), "how am I doing?");
      await user.click(screen.getByRole("button", { name: "Send" }));
      await screen.findByText("Up 2% today.");

      expect(screen.getAllByTestId("chat-bubble").map((li) => li.textContent)).toEqual([
        expect.stringContaining("stored greeting"),
        expect.stringContaining("how am I doing?"),
        expect.stringContaining("Up 2% today."),
      ]);
    });

    it("counts only real messages under the chat-bubble testid", async () => {
      const user = userEvent.setup();
      let resolveChat!: (value: { message: string }) => void;
      api.sendChat.mockReturnValue(new Promise((r) => (resolveChat = r)));
      renderChat();
      await waitFor(() => expect(screen.getByLabelText("Message FinAlly")).toBeEnabled());

      // Empty-state placeholder is an <li> but must not count as a message.
      expect(screen.queryAllByTestId("chat-bubble")).toHaveLength(0);

      await user.type(screen.getByLabelText("Message FinAlly"), "hi");
      await user.click(screen.getByRole("button", { name: "Send" }));

      // Thinking indicator is an <li> too; still only the user bubble is a message.
      expect(screen.getByRole("status")).toBeInTheDocument();
      expect(screen.getAllByTestId("chat-bubble")).toHaveLength(1);

      resolveChat({ message: "Hello." });
      await waitFor(() => expect(screen.getAllByTestId("chat-bubble")).toHaveLength(2));
    });
  });

  it("keeps Send disabled until the draft has content", async () => {
    const user = userEvent.setup();
    const input = await openChat();

    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    await user.type(input, "hi");
    expect(screen.getByRole("button", { name: "Send" })).toBeEnabled();
  });
});
