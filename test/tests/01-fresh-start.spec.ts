import { expect, test } from "@playwright/test";

/**
 * TEST-05 fresh-start scenario, run against the containerized production
 * image (docker-compose.test.yml's `app` service), not a dev server.
 *
 * Numeric filename prefix is deliberate: Playwright runs spec files in
 * sorted order and every spec in this suite shares one seeded portfolio
 * inside one app container, so this spec must run before any spec that
 * mutates state (buys/sells/watchlist changes in later 04-04 specs).
 *
 * Because this spec runs first against a fresh ephemeral (tmpfs) database,
 * the absolute $10,000.00 cash assertion below is safe here; every later
 * spec must assert deltas instead.
 */

const SEEDED_TICKERS = [
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

test("fresh start renders seeded watchlist, $10,000 cash, and streams live prices", async ({
  page,
}) => {
  await page.goto("/");

  // 1. Page shell renders -- same marker scripts/smoke.sh greps for in the
  // served HTML, so a mismatch here means the static export was not wired
  // into the image correctly.
  const terminalRoot = page.getByTestId("terminal-root");
  await expect(terminalRoot).toBeVisible();

  // 2. Watchlist grid renders exactly the ten seeded tickers -- an extra
  // unexpected row must fail this test rather than pass silently.
  const watchlistGrid = page.getByTestId("watchlist-grid");
  await expect(watchlistGrid).toBeVisible();

  for (const ticker of SEEDED_TICKERS) {
    await expect(page.getByTestId(`watchlist-row-${ticker}`)).toBeVisible();
  }

  const rowCount = await watchlistGrid.locator("tbody tr").count();
  expect(rowCount).toBe(10);

  // 3. Header shows the seeded $10,000.00 cash balance.
  await expect(terminalRoot.locator("header")).toContainText("10,000.00");

  // 4. Prices are actually streaming, not merely rendered placeholders:
  // the connection indicator reaches "open", and a watched ticker's
  // displayed price changes within a bounded wait (simulator ticks at
  // roughly 500ms). A dash placeholder must not satisfy this assertion.
  await expect(terminalRoot.locator("header")).toContainText("Connection: open");

  const firstTickerPriceCell = page
    .getByTestId(`watchlist-row-${SEEDED_TICKERS[0]}`)
    .locator("td")
    .nth(1);

  await expect
    .poll(async () => firstTickerPriceCell.textContent(), { timeout: 10000 })
    .not.toBe("--");

  const initialPrice = await firstTickerPriceCell.textContent();
  await expect
    .poll(async () => firstTickerPriceCell.textContent(), { timeout: 10000 })
    .not.toBe(initialPrice);
});
