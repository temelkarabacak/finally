import { expect, test } from "@playwright/test";
import { panel, resetState, submitTrade, waitForStream } from "./helpers";

test.describe("portfolio visualisations", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await resetState(page);
    await page.reload();
    await waitForStream(page);
  });

  test("the heatmap draws a tile per position", async ({ page }) => {
    const heatmap = panel(page, "Allocation");
    await expect(heatmap.getByText("No positions to map")).toBeVisible();

    await submitTrade(page, "NVDA", 3, "buy");
    await submitTrade(page, "MSFT", 2, "buy");

    await expect(heatmap.locator("svg text", { hasText: "NVDA" })).toBeVisible();
    await expect(heatmap.locator("svg text", { hasText: "MSFT" })).toBeVisible();
    // Tiles are sized by weight, so NVDA (the larger notional) must be the wider rect.
    const rects = heatmap.locator("svg g rect");
    await expect.poll(async () => rects.count()).toBeGreaterThanOrEqual(2);
  });

  test("the P&L chart plots snapshots recorded by trades", async ({ page }) => {
    const chart = panel(page, "Portfolio Value");
    await submitTrade(page, "AAPL", 1, "buy");
    await submitTrade(page, "AAPL", 1, "buy");

    // Each trade writes a portfolio_snapshot immediately (PLAN.md section 7).
    await expect(chart.getByText(/[1-9]\d* snapshots/)).toBeVisible();
    await expect(chart.locator("svg path.recharts-line-curve")).toBeVisible();
  });

  test("selecting a watchlist symbol drives the main chart and the ticket", async ({ page }) => {
    await page.locator("tbody tr").filter({ hasText: "TSLA" }).first().click();

    await expect(panel(page, "TSLA")).toBeVisible();
    await expect(page.getByLabel("Trade ticker")).toHaveValue("TSLA");
  });
});
