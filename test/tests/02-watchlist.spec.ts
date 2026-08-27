import { expect, test } from "@playwright/test";

/**
 * TEST-05 watchlist add/remove scenario, run against the containerized
 * production image (docker-compose.test.yml's `webapp` service).
 *
 * Runs after 01-fresh-start.spec.ts (which owns the only absolute-cash
 * assertion in this suite) and before 03-trading.spec.ts, which needs the
 * watchlist back in its pristine ten-ticker state. PYPL is not among the
 * ten seeded tickers, so adding and removing it cannot collide with seed
 * data or with any other spec's assertions.
 */

test("adding and removing a ticker updates the watchlist grid", async ({ page }) => {
  await page.goto("/");

  const watchlistGrid = page.getByTestId("watchlist-grid");
  await expect(watchlistGrid).toBeVisible();

  const initialRowCount = await watchlistGrid.locator("tbody tr").count();

  await page.getByTestId("watchlist-add-input").fill("PYPL");
  await page.getByRole("button", { name: "Add", exact: true }).click();

  const pyplRow = page.getByTestId("watchlist-row-PYPL");
  await expect(pyplRow).toBeVisible();
  await expect(watchlistGrid.locator("tbody tr")).toHaveCount(initialRowCount + 1);

  // Leave the watchlist exactly as found -- later specs assume the ten
  // seeded tickers and nothing else.
  await page.getByRole("button", { name: "Remove PYPL" }).click();

  await expect(pyplRow).not.toBeAttached();
  await expect(watchlistGrid.locator("tbody tr")).toHaveCount(initialRowCount);
});
