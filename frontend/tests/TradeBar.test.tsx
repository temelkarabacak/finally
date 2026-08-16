import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TradeBar } from "@/components/TradeBar";
import { TerminalProvider } from "@/hooks/useTerminal";
import { ApiError } from "@/lib/api";
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

const renderTradeBar = () => render(<TradeBar />, { wrapper: TerminalProvider });

beforeEach(() => {
  vi.clearAllMocks();
  api.fetchPortfolio.mockResolvedValue(fixtures.portfolio);
  api.fetchWatchlist.mockResolvedValue(fixtures.watchlist);
  api.fetchHistory.mockResolvedValue(fixtures.history);
  api.executeTrade.mockResolvedValue(undefined);
});

describe("TradeBar", () => {
  it("prefills the first watchlist symbol and its last price", async () => {
    renderTradeBar();

    await waitFor(() => expect(screen.getByLabelText("Trade ticker")).toHaveValue("AAPL"));
    expect(await screen.findByText("110.00")).toBeInTheDocument();
  });

  it("submits a fractional buy at market", async () => {
    const user = userEvent.setup();
    renderTradeBar();
    await waitFor(() => expect(screen.getByLabelText("Trade ticker")).toHaveValue("AAPL"));

    await user.type(screen.getByLabelText("Trade quantity"), "2.5");
    await user.click(screen.getByRole("button", { name: "Buy" }));

    await waitFor(() =>
      expect(api.executeTrade).toHaveBeenCalledWith({
        ticker: "AAPL",
        quantity: 2.5,
        side: "buy",
      }),
    );
    expect(await screen.findByText("Bought 2.5 AAPL")).toBeInTheDocument();
  });

  it("shows the estimated notional before submitting", async () => {
    const user = userEvent.setup();
    renderTradeBar();
    await waitFor(() => expect(screen.getByLabelText("Trade ticker")).toHaveValue("AAPL"));

    await user.type(screen.getByLabelText("Trade quantity"), "3");

    // 3 shares at the live 110.00 mark
    expect(await screen.findByText("$330.00")).toBeInTheDocument();
  });

  it("sells with the sell button", async () => {
    const user = userEvent.setup();
    renderTradeBar();
    await waitFor(() => expect(screen.getByLabelText("Trade ticker")).toHaveValue("AAPL"));

    await user.type(screen.getByLabelText("Trade quantity"), "1");
    await user.click(screen.getByRole("button", { name: "Sell" }));

    await waitFor(() =>
      expect(api.executeTrade).toHaveBeenCalledWith({ ticker: "AAPL", quantity: 1, side: "sell" }),
    );
  });

  it("surfaces a rejection verbatim and does not clear the quantity", async () => {
    const user = userEvent.setup();
    api.executeTrade.mockRejectedValue(new ApiError("Insufficient cash: need $99,000.00", 400));
    renderTradeBar();
    await waitFor(() => expect(screen.getByLabelText("Trade ticker")).toHaveValue("AAPL"));

    await user.type(screen.getByLabelText("Trade quantity"), "900");
    await user.click(screen.getByRole("button", { name: "Buy" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Insufficient cash");
    expect(screen.getByLabelText("Trade quantity")).toHaveValue("900");
  });

  it("rejects a non-positive quantity without calling the API", async () => {
    const user = userEvent.setup();
    renderTradeBar();
    await waitFor(() => expect(screen.getByLabelText("Trade ticker")).toHaveValue("AAPL"));

    await user.click(screen.getByRole("button", { name: "Buy" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("positive quantity");
    expect(api.executeTrade).not.toHaveBeenCalled();
  });
});
