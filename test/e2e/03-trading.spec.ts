import { expect, test } from "@playwright/test";
import {
  panel,
  parseNumber,
  positionRow,
  readHeaderNumber,
  resetState,
  submitTrade,
  waitForStream,
  watchlistRow,
} from "./helpers";

test.describe("trading", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await resetState(page);
    await page.reload();
    await waitForStream(page);
  });

  test("buying moves cash into a position", async ({ page }) => {
    const cashBefore = await readHeaderNumber(page, "Cash");
    const last = parseNumber(await watchlistRow(page, "AAPL").getByTestId("price-cell").textContent());

    await submitTrade(page, "AAPL", 5, "buy");

    const row = positionRow(page, "AAPL");
    await expect(row).toBeVisible();
    await expect(row.locator("td").nth(1)).toHaveText("5");

    await expect
      .poll(() => readHeaderNumber(page, "Cash"))
      .toBeLessThan(cashBefore - last * 4);
    const cashAfter = await readHeaderNumber(page, "Cash");
    // Prices tick between the read and the fill, so allow a small drift per share.
    expect(cashBefore - cashAfter).toBeGreaterThan(last * 4.5);
    expect(cashBefore - cashAfter).toBeLessThan(last * 5.5);

    // Cash left the balance but stayed in the book: total value barely moves.
    const total = await readHeaderNumber(page, "Portfolio Value");
    expect(Math.abs(total - cashBefore)).toBeLessThan(last * 0.5);
  });

  test("selling the whole position returns the cash and clears the row", async ({ page }) => {
    await submitTrade(page, "MSFT", 2, "buy");
    await expect(positionRow(page, "MSFT")).toBeVisible();

    const cashBefore = await readHeaderNumber(page, "Cash");
    await submitTrade(page, "MSFT", 2, "sell");

    await expect(positionRow(page, "MSFT")).toHaveCount(0);
    await expect(panel(page, "Positions").getByText("No open positions")).toBeVisible();
    await expect.poll(() => readHeaderNumber(page, "Cash")).toBeGreaterThan(cashBefore);
  });

  test("a partial sell leaves the remaining shares", async ({ page }) => {
    await submitTrade(page, "NVDA", 4, "buy");
    await submitTrade(page, "NVDA", 1.5, "sell");

    await expect(positionRow(page, "NVDA").locator("td").nth(1)).toHaveText("2.5");
  });

  test("an oversized sell is rejected outright, not clamped", async ({ page }) => {
    await submitTrade(page, "TSLA", 1, "buy");

    await page.getByLabel("Trade ticker").fill("TSLA");
    await page.getByLabel("Trade quantity").fill("50");
    await page.getByRole("button", { name: "Sell", exact: true }).click();

    await expect(panel(page, "Ticket").getByRole("alert")).toBeVisible();
    // The position is untouched — no partial fill.
    await expect(positionRow(page, "TSLA").locator("td").nth(1)).toHaveText("1");
  });

  test("a buy beyond the cash balance is rejected", async ({ page }) => {
    await page.getByLabel("Trade ticker").fill("NFLX");
    await page.getByLabel("Trade quantity").fill("100000");
    await page.getByRole("button", { name: "Buy", exact: true }).click();

    await expect(panel(page, "Ticket").getByRole("alert")).toBeVisible();
    await expect(positionRow(page, "NFLX")).toHaveCount(0);
  });
});
