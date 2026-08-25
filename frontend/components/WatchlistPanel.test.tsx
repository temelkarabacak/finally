import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";

import { WatchlistPanel } from "@/components/WatchlistPanel";
import type { PriceTick } from "@/hooks/usePriceStream";

function makeTick(overrides: Partial<PriceTick> = {}): PriceTick {
  return {
    ticker: "AAPL",
    price: 190,
    previous_price: 189,
    timestamp: Date.now() / 1000,
    change: 1,
    change_percent: 0.5,
    direction: "up",
    ...overrides,
  };
}

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

const SEEDED_WATCHLIST = [
  {
    ticker: "AAPL",
    price: null,
    previous_price: null,
    change: null,
    change_percent: null,
    direction: null,
  },
];

function renderPanel(prices: Record<string, PriceTick> = {}) {
  return render(
    <WatchlistPanel prices={prices} history={{}} selected={null} onSelect={() => {}} />,
  );
}

describe("WatchlistPanel", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    global.fetch = fetchMock as unknown as typeof fetch;
  });

  afterEach(() => {
    cleanup();
  });

  it("flashes flash-up on the row when the price ticks up", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, SEEDED_WATCHLIST));
    const { rerender } = renderPanel({});
    await waitFor(() => expect(screen.getByTestId("watchlist-row-AAPL")).toBeInTheDocument());

    // First rerender establishes the baseline price (no prior price to compare against).
    rerender(
      <WatchlistPanel
        prices={{ AAPL: makeTick({ price: 190, direction: "flat" }) }}
        history={{}}
        selected={null}
        onSelect={() => {}}
      />,
    );

    rerender(
      <WatchlistPanel
        prices={{ AAPL: makeTick({ price: 195, direction: "up" }) }}
        history={{}}
        selected={null}
        onSelect={() => {}}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("watchlist-row-AAPL")).toHaveClass("flash-up");
    });
  });

  it("flashes flash-down on the row when the price ticks down", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, SEEDED_WATCHLIST));
    const { rerender } = renderPanel({});
    await waitFor(() => expect(screen.getByTestId("watchlist-row-AAPL")).toBeInTheDocument());

    rerender(
      <WatchlistPanel
        prices={{ AAPL: makeTick({ price: 190, direction: "flat" }) }}
        history={{}}
        selected={null}
        onSelect={() => {}}
      />,
    );

    rerender(
      <WatchlistPanel
        prices={{ AAPL: makeTick({ price: 185, direction: "down" }) }}
        history={{}}
        selected={null}
        onSelect={() => {}}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("watchlist-row-AAPL")).toHaveClass("flash-down");
    });
  });

  it("applies neither flash class when the price repeats identically", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, SEEDED_WATCHLIST));
    const { rerender } = renderPanel({});
    await waitFor(() => expect(screen.getByTestId("watchlist-row-AAPL")).toBeInTheDocument());

    rerender(
      <WatchlistPanel
        prices={{ AAPL: makeTick({ price: 190, direction: "up" }) }}
        history={{}}
        selected={null}
        onSelect={() => {}}
      />,
    );

    rerender(
      <WatchlistPanel
        prices={{ AAPL: makeTick({ price: 190, direction: "up" }) }}
        history={{}}
        selected={null}
        onSelect={() => {}}
      />,
    );

    await waitFor(() => {
      const row = screen.getByTestId("watchlist-row-AAPL");
      expect(row).not.toHaveClass("flash-up");
      expect(row).not.toHaveClass("flash-down");
    });
  });

  it("clears the flash class when the CSS animation ends", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, SEEDED_WATCHLIST));
    const { rerender } = renderPanel({});
    await waitFor(() => expect(screen.getByTestId("watchlist-row-AAPL")).toBeInTheDocument());

    rerender(
      <WatchlistPanel
        prices={{ AAPL: makeTick({ price: 190, direction: "flat" }) }}
        history={{}}
        selected={null}
        onSelect={() => {}}
      />,
    );
    rerender(
      <WatchlistPanel
        prices={{ AAPL: makeTick({ price: 195, direction: "up" }) }}
        history={{}}
        selected={null}
        onSelect={() => {}}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("watchlist-row-AAPL")).toHaveClass("flash-up");
    });

    fireEvent.animationEnd(screen.getByTestId("watchlist-row-AAPL"));

    await waitFor(() => {
      expect(screen.getByTestId("watchlist-row-AAPL")).not.toHaveClass("flash-up");
    });
  });

  it("POSTs the uppercased ticker and refetches the grid on a successful add", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(200, SEEDED_WATCHLIST)) // initial GET on mount
      .mockResolvedValueOnce(jsonResponse(201, { ticker: "PYPL" })) // POST /api/watchlist
      .mockResolvedValueOnce(jsonResponse(200, SEEDED_WATCHLIST)); // refetch GET

    renderPanel({});
    await waitFor(() => expect(screen.getByTestId("watchlist-row-AAPL")).toBeInTheDocument());

    fireEvent.change(screen.getByTestId("watchlist-add-input"), {
      target: { value: "pypl" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));

    const [postUrl, postInit] = fetchMock.mock.calls[1];
    expect(postUrl).toBe("/api/watchlist");
    expect(postInit.method).toBe("POST");
    expect(JSON.parse(postInit.body as string)).toEqual({ ticker: "PYPL" });

    const [refetchUrl] = fetchMock.mock.calls[2];
    expect(refetchUrl).toBe("/api/watchlist");
  });

  it("shows the already-on-the-watchlist message on a 409 and keeps the input value", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(200, SEEDED_WATCHLIST)) // initial GET
      .mockResolvedValueOnce(jsonResponse(409, { detail: "Ticker already on watchlist" })); // POST

    renderPanel({});
    await waitFor(() => expect(screen.getByTestId("watchlist-row-AAPL")).toBeInTheDocument());

    const input = screen.getByTestId("watchlist-add-input") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "AAPL" } });
    fireEvent.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() => {
      expect(screen.getByText("AAPL is already on the watchlist")).toBeInTheDocument();
    });
    expect(input.value).toBe("AAPL");
  });

  it("DELETEs the ticker and refetches the grid on a successful remove", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(200, SEEDED_WATCHLIST)) // initial GET
      .mockResolvedValueOnce(jsonResponse(204, null)) // DELETE
      .mockResolvedValueOnce(jsonResponse(200, [])); // refetch GET

    renderPanel({});
    await waitFor(() => expect(screen.getByTestId("watchlist-row-AAPL")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Remove AAPL" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));

    const [deleteUrl, deleteInit] = fetchMock.mock.calls[1];
    expect(deleteUrl).toBe("/api/watchlist/AAPL");
    expect(deleteInit.method).toBe("DELETE");
  });

  it("shows the not-on-the-watchlist message on a 404 remove", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(200, SEEDED_WATCHLIST)) // initial GET
      .mockResolvedValueOnce(jsonResponse(404, { detail: "Ticker not on watchlist" })) // DELETE
      .mockResolvedValueOnce(jsonResponse(200, SEEDED_WATCHLIST)); // refetch after 404

    renderPanel({});
    await waitFor(() => expect(screen.getByTestId("watchlist-row-AAPL")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Remove AAPL" }));

    await waitFor(() => {
      expect(screen.getByText("AAPL is not on the watchlist")).toBeInTheDocument();
    });
  });
});
