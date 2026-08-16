# FinAlly Frontend

Next.js static export served by the FastAPI backend. See `CLAUDE.md` for architecture and
conventions.

```bash
npm install
npm run dev      # :3100, proxies /api to the backend on :8000
npm run build    # static export -> out/
npm test         # vitest
```

To work without the backend, run the mock API in a second terminal:

```bash
npm run mock     # :8001
npm run dev:mock # :3100, pointed at the mock
```

Open http://localhost:3100 — not `127.0.0.1`, which Next's dev-origin check blocks.
