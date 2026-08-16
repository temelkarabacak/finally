import { expect, type Locator, type Page } from "@playwright/test";

export const DEFAULT_TICKERS = [
  "AAPL",
  "GOOGL",
  "MSFT",
  "AMZN",
  "TSLA",
  "NVDA",
  "META",
  "JPM",
  "V",
  "NFLX",
];

/** "$10,000.00" / "+$12.40" / "-1.25%" -> number */
export function parseNumber(text: string | null): number {
  if (!text) return NaN;
  const cleaned = text.replace(/[^0-9.+-]/g, "");
  return Number(cleaned);
}

/** The framed section whose header label matches, e.g. "Watchlist". */
export function panel(page: Page, label: string): Locator {
  return page.locator("section").filter({ has: page.locator(`h2:text-is("${label}")`) });
}

/** A header readout value, e.g. headerValue(page, "Cash"). */
export function headerValue(page: Page, label: string): Locator {
  return page.locator(`header span.panel-label:text-is("${label}") + span`);
}

export async function readHeaderNumber(page: Page, label: string): Promise<number> {
  return parseNumber(await headerValue(page, label).textContent());
}

export function watchlistRow(page: Page, ticker: string): Locator {
  return panel(page, "Watchlist")
    .locator("tbody tr")
    .filter({ has: page.locator(`span:text-is("${ticker}")`) });
}

export function positionRow(page: Page, ticker: string): Locator {
  return panel(page, "Positions")
    .locator("tbody tr")
    .filter({ has: page.locator(`td:text-is("${ticker}")`) });
}

/** Total SSE ticks received since page load, from the status rail. */
export async function tickCount(page: Page): Promise<number> {
  const text = await page.locator("footer span.num", { hasText: "TICKS" }).textContent();
  return parseNumber(text);
}

/** Waits until the SSE feed is connected and has delivered at least `min` ticks. */
export async function waitForStream(page: Page, min = 1): Promise<void> {
  await expect(page.getByTestId("connection-dot")).toHaveAttribute("data-state", "connected");
  await expect.poll(() => tickCount(page), { timeout: 20_000 }).toBeGreaterThanOrEqual(min);
}

/** Places a market order through the trade ticket and waits for the receipt. */
export async function submitTrade(
  page: Page,
  ticker: string,
  qty: number,
  side: "buy" | "sell",
): Promise<void> {
  await page.getByLabel("Trade ticker").fill(ticker);
  await page.getByLabel("Trade quantity").fill(String(qty));
  await page.getByRole("button", { name: side === "buy" ? "Buy" : "Sell", exact: true }).click();
  await expect(panel(page, "Ticket").getByRole("status")).toHaveText(
    new RegExp(`^${side === "buy" ? "Bought" : "Sold"} `),
  );
}

/** Only the message bubbles — not the placeholder or the "thinking" indicator. */
export function chatBubbles(page: Page): Locator {
  return page.getByTestId("chat-log").getByTestId("chat-bubble");
}

/**
 * Resolves once the panel has finished rehydrating from `/api/chat/history`.
 * The input stays disabled until then, so being enabled is the panel's own
 * readiness signal rather than a guess about timing.
 */
export async function waitForChatReady(page: Page): Promise<Locator> {
  const input = page.getByLabel("Message FinAlly");
  await expect(input).toBeEnabled();
  return input;
}

/** Sends a chat message and waits for the assistant bubble to arrive. */
export async function sendChat(page: Page, text: string): Promise<Locator> {
  const input = await waitForChatReady(page);
  const bubbles = chatBubbles(page);
  const before = await bubbles.count();

  await input.fill(text);
  await page.getByRole("button", { name: "Send" }).click();

  // The user bubble plus the assistant bubble.
  await expect(bubbles).toHaveCount(before + 2, { timeout: 40_000 });
  return bubbles.last();
}

/** Resets server state so each spec starts from the seeded defaults. */
export async function resetState(page: Page): Promise<void> {
  const portfolio = await (await page.request.get("/api/portfolio")).json();
  for (const position of portfolio.positions) {
    await page.request.post("/api/portfolio/trade", {
      data: { ticker: position.ticker, quantity: position.quantity, side: "sell" },
    });
  }
  const watchlist = await (await page.request.get("/api/watchlist")).json();
  const watched = new Set<string>(watchlist.map((entry: { ticker: string }) => entry.ticker));
  for (const ticker of watched) {
    if (!DEFAULT_TICKERS.includes(ticker)) {
      await page.request.delete(`/api/watchlist/${ticker}`);
    }
  }
  for (const ticker of DEFAULT_TICKERS) {
    if (!watched.has(ticker)) {
      await page.request.post("/api/watchlist", { data: { ticker } });
    }
  }
}
