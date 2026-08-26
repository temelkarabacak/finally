import { expect, type Page, test } from "@playwright/test";

/**
 * TEST-05 buy/sell scenario, run against the containerized production image.
 *
 * Runs after 02-watchlist.spec.ts and before 04-visualizations.spec.ts,
 * which depends on the one open AAPL share this spec deliberately leaves
 * behind. Only 01-fresh-start.spec.ts gets to assert an absolute cash
 * figure (it alone sees the pristine seeded balance) -- every trade here
 * asserts a delta relative to a baseline read immediately before the
 * action, because prices tick roughly every 500ms and cash is read fresh
 * each time rather than computed from a remembered arithmetic result.
 */

/** Parses the header's "Cash 1,234.56"-style text into a bare number. */
async function readCash(page: Page): Promise<number> {
  const headerText = await page.locator("header").innerText();
  const match = headerText.match(/Cash\s+\$?([\d,]+\.\d{2})/);
  if (!match) {
    throw new Error(`could not find a cash figure in header text: ${headerText}`);
  }
  return Number(match[1].replace(/,/g, ""));
}

test("buying then selling AAPL updates cash and the positions table", async ({ page }) => {
  await page.goto("/");

  const positionsGrid = page.getByTestId("positions-grid");

  // Buy 2 AAPL.
  const cashBeforeBuy = await readCash(page);
  await page.getByTestId("trade-ticker-input").fill("AAPL");
  await page.getByTestId("trade-quantity-input").fill("2");
  await page.getByRole("button", { name: "Buy", exact: true }).click();

  await expect.poll(() => readCash(page), { timeout: 10_000 }).toBeLessThan(cashBeforeBuy);
  await expect(positionsGrid).toBeVisible();

  const aaplRow = positionsGrid.getByRole("row", { name: /AAPL/ });
  await expect(aaplRow).toBeVisible();
  await expect(aaplRow.locator("td").nth(1)).toHaveText("2");

  // portfolio_snapshots are keyed to whole seconds (backend/app/portfolio/
  // snapshots.py), and 04-visualizations.spec.ts needs at least two
  // distinct points to leave the P&L chart's empty state -- both trades in
  // this spec write a snapshot, but back-to-back requests can land in the
  // same second and collapse to one point. A short, bounded wait forces
  // this sell into a different second than the buy above.
  await page.waitForTimeout(1100);

  // Sell 1 of the 2 AAPL shares just bought, leaving exactly 1 share open
  // for 04-visualizations.spec.ts.
  const cashAfterBuy = await readCash(page);
  await page.getByTestId("trade-ticker-input").fill("AAPL");
  await page.getByTestId("trade-quantity-input").fill("1");
  await page.getByRole("button", { name: "Sell", exact: true }).click();

  await expect.poll(() => readCash(page), { timeout: 10_000 }).toBeGreaterThan(cashAfterBuy);
  await expect(aaplRow.locator("td").nth(1)).toHaveText("1");
});
