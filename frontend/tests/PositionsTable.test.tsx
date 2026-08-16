import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PositionsTable } from "@/components/PositionsTable";
import { TerminalProvider } from "@/hooks/useTerminal";
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

beforeEach(() => {
  vi.clearAllMocks();
  api.fetchPortfolio.mockResolvedValue(fixtures.portfolio);
  api.fetchWatchlist.mockResolvedValue(fixtures.watchlist);
  api.fetchHistory.mockResolvedValue(fixtures.history);
});

/** Cells of the row whose first cell is `ticker`, as trimmed text. */
async function rowFor(ticker: string) {
  const cell = await screen.findByText(ticker);
  return [...cell.closest("tr")!.querySelectorAll("td")].map((td) => td.textContent?.trim());
}

describe("PositionsTable", () => {
  it("shows a profitable position with signed P&L and percent", async () => {
    render(<PositionsTable />, { wrapper: TerminalProvider });

    // 10 @ 100 cost, marked at 110 -> $1,100 value, +$100, +10.00%
    expect(await rowFor("AAPL")).toEqual([
      "AAPL",
      "10",
      "100.00",
      "110.00",
      "$1,100.00",
      "+$100.00",
      "+10.00%",
    ]);
  });

  it("shows a losing position with a negative P&L", async () => {
    render(<PositionsTable />, { wrapper: TerminalProvider });

    // 4 @ 250 cost, marked at 200 -> $800 value, -$200, -20.00%
    const cells = await rowFor("TSLA");
    expect(cells.slice(4)).toEqual(["$800.00", "-$200.00", "-20.00%"]);
  });

  it("tints P&L cells green for gains and red for losses", async () => {
    render(<PositionsTable />, { wrapper: TerminalProvider });
    await screen.findByText("AAPL");

    expect(screen.getByText("+$100.00").className).toContain("text-gain");
    expect(screen.getByText("-$200.00").className).toContain("text-loss");
  });

  it("summarises net unrealized P&L in the panel header", async () => {
    render(<PositionsTable />, { wrapper: TerminalProvider });

    // +100 on AAPL, -200 on TSLA
    expect(await screen.findByText("-$100.00")).toBeInTheDocument();
    expect(screen.getByText("2 open")).toBeInTheDocument();
  });

  it("prompts when there are no positions", async () => {
    api.fetchPortfolio.mockResolvedValue({ ...fixtures.portfolio, positions: [] });
    render(<PositionsTable />, { wrapper: TerminalProvider });

    expect(await screen.findByText(/No open positions/)).toBeInTheDocument();
  });
});
