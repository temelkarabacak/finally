import { expect, test } from "@playwright/test";

/**
 * TEST-05 SSE reconnection scenario, run against the containerized
 * production image.
 *
 * `context.setOffline(true)` throttles bandwidth to zero but does not
 * terminate an already-open streaming connection in this Chromium/CDP
 * setup -- confirmed empirically: an open EventSource's readyState stayed
 * OPEN for a full 60 seconds under setOffline alone, because CDP network
 * emulation stalls reads rather than erroring the socket, and the frontend
 * only reacts to a genuine EventSource 'error'. setOffline is still called
 * below (it matches this scenario's intent and genuinely blocks any other
 * outgoing request during the simulated outage), paired with a route
 * interception that fails the stream endpoint outright and a reload to
 * force a fresh connection attempt against it -- an aborted connection
 * attempt is a real failure EventSource's error handling reacts to, unlike
 * a merely-throttled one. Recovery is verified without a second reload:
 * once the endpoint is let through again, EventSource's own native retry
 * (no custom retry logic in this app -- see usePriceStream.ts) must
 * reconnect and resume streaming on its own.
 */

test("dropping and restoring the network reconnects the price stream", async ({
  page,
  context,
}) => {
  let simulateOutage = false;

  await page.route("**/api/stream/prices", async (route) => {
    if (simulateOutage) {
      await route.abort("connectionrefused");
    } else {
      await route.continue();
    }
  });

  await page.goto("/");
  const header = page.locator("header");
  await expect(header).toContainText("Connection: open");

  // Reload while the route interception is armed but before marking the
  // context offline -- setOffline blocks new top-level navigations too
  // (confirmed empirically: page.reload() itself fails with
  // net::ERR_INTERNET_DISCONNECTED once offline), and the reload needs to
  // succeed so only the stream endpoint, not the whole page shell, is down.
  simulateOutage = true;
  await page.reload();
  await context.setOffline(true);

  await expect(header).not.toContainText("Connection: open", { timeout: 15_000 });

  await context.setOffline(false);
  simulateOutage = false;
  await expect(header).toContainText("Connection: open", { timeout: 20_000 });

  // Prove the stream genuinely resumed -- not just that the indicator
  // flipped -- by watching a watched ticker's price change again.
  const priceCell = page.getByTestId("watchlist-row-AAPL").locator("td").nth(1);
  const priceAfterReconnect = await priceCell.textContent();
  await expect
    .poll(async () => priceCell.textContent(), { timeout: 15_000 })
    .not.toBe(priceAfterReconnect);
});
