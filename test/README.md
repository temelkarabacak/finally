# E2E Tests

Playwright suite that drives the real Docker image in a browser.

```bash
docker compose -f test/docker-compose.test.yml up --build --exit-code-from playwright
docker compose -f test/docker-compose.test.yml down -v
```

`docker-compose.test.yml` starts two containers: the production image (`LLM_MOCK=true`, a
tmpfs `/app/db` so every run gets a freshly seeded database) and the official Playwright
image, which keeps browser dependencies out of the app image. Exit code 0 means green.

To iterate against a container you already have running:

```bash
docker run -d --name finally-e2e-dev -p 8100:8000 -e LLM_MOCK=true --tmpfs /app/db finally:latest
npm install --prefix test && npx --prefix test playwright install chromium
BASE_URL=http://localhost:8100 npx playwright test --config test/playwright.config.ts
```

## Notes

- Specs run serially against one shared database, so `e2e/01-fresh-start.spec.ts` runs first
  and is the only one allowed to assert the exact $10,000 starting balance. The rest call
  `resetState()` and assert relative changes.
- Chat assertions rely on the `LLM_MOCK` rules in `backend/app/llm/mock.py`, which only match
  UPPERCASE tickers.
- The app service is deliberately **not** named `app`: the `.app` TLD is HSTS-preloaded, so
  Chrome rewrites `http://app:8000` to HTTPS and every navigation fails.
