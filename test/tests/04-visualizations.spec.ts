import { expect, test } from "@playwright/test";

/**
 * TEST-05 heatmap and P&L chart rendering scenario, run against the
 * containerized production image.
 *
 * Depends on 03-trading.spec.ts leaving one open AAPL share behind: without
 * a position, both the heatmap and the P&L chart would legitimately show
 * their empty states. Portfolio snapshots are recorded every 30 seconds and
 * immediately after each trade (planning/PLAN.md §7), so 03-trading's two
 * trades already guarantee history exists by the time this spec runs --
 * no fixed sleep is used, only bounded `expect`/`toBeHidden` waits.
 */

test("heatmap renders the open position and the P&L chart leaves its empty state", async ({
  page,
}) => {
  await page.goto("/");

  // Heatmap: a treemap cell for AAPL, with a genuine percentage in its
  // accessible name -- a rendered-but-empty cell (no percentage) must fail.
  const heatmapCell = page.getByRole("button", { name: /^AAPL:/ });
  await expect(heatmapCell).toBeVisible();
  await expect(heatmapCell).toHaveAccessibleName(
    /^AAPL: [+-]?\d+\.\d+% unrealized P&L$/,
  );

  // P&L chart: the "Building portfolio history" empty-state overlay must be
  // gone, and a canvas with real screen space must be in its place.
  await expect(page.getByText("Building portfolio history")).toBeHidden({ timeout: 10_000 });

  const pnlHeading = page.getByText("P&L", { exact: true });
  const pnlPanel = pnlHeading.locator("xpath=../.."); // heading -> header row -> panel root
  // Lightweight Charts renders several internal canvases per pane (main
  // plot, price axis, time axis, each doubled for pixel-ratio); the first
  // one in DOM order is the main price-pane canvas.
  const pnlCanvas = pnlPanel.locator("canvas").first();

  await expect(pnlCanvas).toBeVisible();
  const box = await pnlCanvas.boundingBox();
  expect(box?.width ?? 0).toBeGreaterThan(0);
  expect(box?.height ?? 0).toBeGreaterThan(0);
});
