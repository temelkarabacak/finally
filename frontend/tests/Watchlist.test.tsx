import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Watchlist } from "@/components/Watchlist";
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

const renderWatchlist = () => render(<Watchlist />, { wrapper: TerminalProvider });

beforeEach(() => {
  vi.clearAllMocks();
  api.fetchPortfolio.mockResolvedValue(fixtures.portfolio);
  api.fetchWatchlist.mockResolvedValue(fixtures.watchlist);
  api.fetchHistory.mockResolvedValue(fixtures.history);
  api.addWatchlistTicker.mockResolvedValue(undefined);
  api.removeWatchlistTicker.mockResolvedValue(undefined);
});

describe("Watchlist", () => {
  it("lists the watched symbols with prices and change", async () => {
    renderWatchlist();

    expect(await screen.findByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("TSLA")).toBeInTheDocument();
    expect(screen.getByText("+1.50%")).toBeInTheDocument();
    expect(screen.getByText("-2.25%")).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(3); // header + two symbols
  });

  it("adds a ticker, uppercasing the input, then refetches", async () => {
    const user = userEvent.setup();
    renderWatchlist();
    await screen.findByText("AAPL");

    await user.type(screen.getByLabelText("Add ticker"), "pypl");
    await user.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() => expect(api.addWatchlistTicker).toHaveBeenCalledWith("PYPL"));
    expect(api.fetchWatchlist).toHaveBeenCalledTimes(2);
    expect(screen.getByLabelText("Add ticker")).toHaveValue("");
  });

  it("surfaces the backend message when an add is rejected", async () => {
    const user = userEvent.setup();
    api.addWatchlistTicker.mockRejectedValue(new ApiError("AAPL is already watched", 409));
    renderWatchlist();
    await screen.findByText("AAPL");

    await user.type(screen.getByLabelText("Add ticker"), "AAPL");
    await user.click(screen.getByRole("button", { name: "Add" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("AAPL is already watched");
  });

  it("removes a ticker", async () => {
    const user = userEvent.setup();
    renderWatchlist();
    await screen.findByText("TSLA");

    await user.click(screen.getByLabelText("Remove TSLA"));

    await waitFor(() => expect(api.removeWatchlistTicker).toHaveBeenCalledWith("TSLA"));
  });

  it("selects a symbol when its row is clicked", async () => {
    const user = userEvent.setup();
    renderWatchlist();

    const row = (await screen.findByText("TSLA")).closest("tr")!;
    await user.click(row);

    expect(row).toHaveAttribute("aria-selected", "true");
  });
});
