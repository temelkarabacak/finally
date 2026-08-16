import { expect, test } from "@playwright/test";
import { tickCount, waitForStream } from "./helpers";

test.describe("SSE resilience", () => {
  test("reconnects on its own once an unreachable feed comes back", async ({ page }) => {
    let reachable = false;
    await page.route("**/api/stream/prices", async (route) => {
      if (reachable) await route.continue();
      else await route.abort("connectionrefused");
    });

    await page.goto("/");

    const dot = page.getByTestId("connection-dot");
    await expect(dot).not.toHaveAttribute("data-state", "connected");
    expect(await tickCount(page)).toBe(0);

    // EventSource honours the server's `retry: 1000`, so no reload and no user
    // action should be needed for the feed to come back.
    reachable = true;
    await expect(dot).toHaveAttribute("data-state", "connected", { timeout: 30_000 });
    await expect.poll(() => tickCount(page), { timeout: 30_000 }).toBeGreaterThan(0);
  });

  test("the feed survives a page reload", async ({ page }) => {
    await page.goto("/");
    await waitForStream(page, 5);

    await page.reload();
    await waitForStream(page, 5);
  });
});
