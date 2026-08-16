import { expect, test } from "@playwright/test";
import { DEFAULT_TICKERS, panel, headerValue, tickCount, waitForStream } from "./helpers";

/**
 * Runs first, against the seeded database, so it can assert the exact
 * starting cash balance before any other spec trades.
 */
test.describe("fresh start", () => {
  test("shows the seeded watchlist, $10,000 cash and a live feed", async ({ page }) => {
    await page.goto("/");

    const rows = panel(page, "Watchlist").locator("tbody tr");
    await expect(rows).toHaveCount(DEFAULT_TICKERS.length);
    for (const ticker of DEFAULT_TICKERS) {
      await expect(rows.filter({ hasText: ticker }).first()).toBeVisible();
    }

    await expect(headerValue(page, "Cash")).toHaveText("$10,000.00");
    await expect(headerValue(page, "Portfolio Value")).toHaveText("$10,000.00");
    await expect(panel(page, "Positions").getByText("No open positions")).toBeVisible();

    await waitForStream(page, 5);
  });

  test("prices keep moving after the first tick", async ({ page }) => {
    await page.goto("/");
    await waitForStream(page);

    const aapl = panel(page, "Watchlist")
      .locator("tbody tr")
      .filter({ hasText: "AAPL" })
      .getByTestId("price-cell");
    const first = await aapl.textContent();

    await expect.poll(async () => aapl.textContent(), { timeout: 20_000 }).not.toBe(first);

    const ticks = await tickCount(page);
    await expect.poll(() => tickCount(page), { timeout: 20_000 }).toBeGreaterThan(ticks);
  });
});
