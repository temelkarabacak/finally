import { expect, test } from "@playwright/test";

/**
 * TEST-05 AI chat scenario, run against the containerized production image
 * with LLM_MOCK=true (set on the compose `webapp` service). The mock
 * matcher in backend/app/llm/mock.py deterministically renders a buy of 2
 * AAPL as the exact string "Buying 2 AAPL." -- asserted verbatim below, not
 * as a loose substring, since that determinism is the entire reason the
 * mock exists.
 *
 * Runs after 03-trading.spec.ts so there is ample cash for the mock-driven
 * buy to validate rather than be rejected for insufficient funds.
 */

test("chat executes a trade and renders an inline confirmation", async ({ page }) => {
  await page.goto("/");

  await page.getByTestId("chat-toggle").click();
  await expect(page.getByTestId("chat-drawer")).toBeVisible();

  await page.getByTestId("chat-input").fill("buy 2 shares of AAPL");
  await page.getByTestId("chat-send").click();

  await expect(page.getByTestId("chat-message-user")).toContainText("buy 2 shares of AAPL");

  const assistantBubble = page.getByTestId("chat-message-assistant");
  await expect(assistantBubble).toHaveText("Buying 2 AAPL.");

  await expect(page.getByTestId("trade-card")).toBeVisible();
  await expect(page.getByTestId("chat-thinking")).toHaveCount(0);
});
