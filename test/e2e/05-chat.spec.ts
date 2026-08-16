import { expect, test } from "@playwright/test";
import {
  panel,
  positionRow,
  resetState,
  sendChat,
  waitForStream,
  watchlistRow,
} from "./helpers";

/**
 * The container runs with LLM_MOCK=true, so the assistant's replies come from
 * `backend/app/llm/mock.py`. Its rules only match UPPERCASE tickers.
 */
test.describe("AI copilot (mocked)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await resetState(page);
    await page.reload();
    await waitForStream(page);
  });

  test("answers a portfolio question without trading", async ({ page }) => {
    const reply = await sendChat(page, "how is my portfolio doing?");

    await expect(reply).toContainText(/cash/i);
    await expect(panel(page, "Positions").getByText("No open positions")).toBeVisible();
  });

  test("executes a chat-driven trade and shows it inline", async ({ page }) => {
    const reply = await sendChat(page, "buy 10 AAPL");

    await expect(reply).toContainText("Executing");
    await expect(reply.getByText(/^BUY 10 AAPL @ /)).toBeVisible();

    // The action really hit the backend, not just the transcript.
    await expect(positionRow(page, "AAPL")).toBeVisible();
    await expect(positionRow(page, "AAPL").locator("td").nth(1)).toHaveText("10");
  });

  test("edits the watchlist on request", async ({ page }) => {
    const reply = await sendChat(page, "add PYPL to the watchlist");

    await expect(reply.getByText("+ PYPL")).toBeVisible();
    await expect(watchlistRow(page, "PYPL")).toBeVisible();
  });

  test("keeps the transcript across a reload", async ({ page }) => {
    await sendChat(page, "buy 1 NVDA");
    await page.reload();

    // The panel rehydrates from /api/chat/history, so the last exchange survives.
    const bubbles = page.getByTestId("chat-log").locator("li");
    await expect(bubbles.last()).toContainText("Executing");
    const count = await bubbles.count();
    await expect(bubbles.nth(count - 2)).toContainText("buy 1 NVDA");
  });
});
