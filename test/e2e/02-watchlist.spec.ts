import { expect, test } from "@playwright/test";
import { panel, resetState, watchlistRow } from "./helpers";

const NEW_TICKER = "PYPL";

test.describe("watchlist", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await resetState(page);
    await page.reload();
  });

  test("adds a ticker, streams it, then removes it", async ({ page }) => {
    const rows = panel(page, "Watchlist").locator("tbody tr");
    await expect(rows).toHaveCount(10);

    await page.getByLabel("Add ticker").fill(NEW_TICKER);
    await page.getByRole("button", { name: "Add", exact: true }).click();

    const added = watchlistRow(page, NEW_TICKER);
    await expect(added).toBeVisible();
    await expect(rows).toHaveCount(11);
    // A newly watched ticker joins the active set, so it must start pricing.
    await expect(added.getByTestId("price-cell")).not.toHaveText("—");

    // It is server state, not just local state.
    await page.reload();
    await expect(watchlistRow(page, NEW_TICKER)).toBeVisible();

    await added.hover();
    await added.getByRole("button", { name: `Remove ${NEW_TICKER}` }).click();
    await expect(watchlistRow(page, NEW_TICKER)).toHaveCount(0);
    await expect(rows).toHaveCount(10);

    await page.reload();
    await expect(watchlistRow(page, NEW_TICKER)).toHaveCount(0);
  });

  test("rejects a duplicate ticker with the backend's reason", async ({ page }) => {
    await page.getByLabel("Add ticker").fill("AAPL");
    await page.getByRole("button", { name: "Add", exact: true }).click();

    await expect(panel(page, "Watchlist").getByRole("alert")).toBeVisible();
    await expect(panel(page, "Watchlist").locator("tbody tr")).toHaveCount(10);
  });
});
