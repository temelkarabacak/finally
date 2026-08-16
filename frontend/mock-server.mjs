/**
 * Development-only stand-in for the FastAPI backend, implementing the contract in
 * planning/PLAN.md §8. Run with `npm run mock` and point the dev server at it via
 * `npm run dev:mock`. Not part of the production build.
 */
import { createServer } from "node:http";
import { randomUUID } from "node:crypto";

const PORT = Number(process.env.MOCK_PORT ?? 8001);

const SEED = {
  AAPL: 190, GOOGL: 175, MSFT: 415, AMZN: 185, TSLA: 245,
  NVDA: 880, META: 500, JPM: 195, V: 275, NFLX: 610,
};

const state = {
  cash: 10000,
  watchlist: Object.keys(SEED),
  positions: new Map(),
  snapshots: [],
  prices: new Map(Object.entries(SEED).map(([t, p]) => [t, { price: p, previous: p }])),
};

const activeTickers = () =>
  [...new Set([...state.watchlist, ...state.positions.keys()])];

function tick() {
  for (const ticker of activeTickers()) {
    const current = state.prices.get(ticker) ?? { price: 100, previous: 100 };
    const drift = (Math.random() - 0.5) * 0.004;
    const next = Math.max(1, current.price * (1 + drift));
    state.prices.set(ticker, { price: Number(next.toFixed(2)), previous: current.price });
  }
}
setInterval(tick, 500);

const positionsValue = () =>
  [...state.positions.entries()].reduce(
    (sum, [ticker, p]) => sum + p.quantity * (state.prices.get(ticker)?.price ?? p.avg_cost),
    0,
  );

setInterval(() => {
  state.snapshots.push({
    total_value: Number((state.cash + positionsValue()).toFixed(2)),
    recorded_at: new Date().toISOString(),
  });
  if (state.snapshots.length > 200) state.snapshots.shift();
}, 3000);

// Backfill so the P&L chart has something on first load.
for (let i = 40; i > 0; i -= 1) {
  state.snapshots.push({
    total_value: 10000 + Math.sin(i / 4) * 60 + (40 - i) * 3,
    recorded_at: new Date(Date.now() - i * 30_000).toISOString(),
  });
}

const send = (res, status, body) => {
  const payload = JSON.stringify(body);
  res.writeHead(status, { "Content-Type": "application/json", "Cache-Control": "no-store" });
  res.end(payload);
};

const readBody = (req) =>
  new Promise((resolve) => {
    let raw = "";
    req.on("data", (chunk) => (raw += chunk));
    req.on("end", () => resolve(raw ? JSON.parse(raw) : {}));
  });

function portfolio() {
  const positions = [...state.positions.entries()].map(([ticker, p]) => {
    const current = state.prices.get(ticker)?.price ?? p.avg_cost;
    const marketValue = p.quantity * current;
    const cost = p.quantity * p.avg_cost;
    return {
      ticker,
      quantity: p.quantity,
      avg_cost: p.avg_cost,
      current_price: current,
      market_value: marketValue,
      unrealized_pnl: marketValue - cost,
      pnl_percent: cost ? ((marketValue - cost) / cost) * 100 : 0,
    };
  });
  const value = positions.reduce((sum, p) => sum + p.market_value, 0);
  return {
    cash_balance: state.cash,
    positions,
    total_value: state.cash + value,
    unrealized_pnl: positions.reduce((sum, p) => sum + p.unrealized_pnl, 0),
  };
}

function applyTrade({ ticker, quantity, side }) {
  const symbol = String(ticker).toUpperCase();
  const qty = Number(quantity);
  if (!symbol || !(qty > 0)) return { error: "Quantity must be a positive number" };

  const price = state.prices.get(symbol)?.price;
  if (!price) return { error: `No market data for ${symbol}` };

  const held = state.positions.get(symbol);

  if (side === "buy") {
    const cost = qty * price;
    if (cost > state.cash) {
      return { error: `Insufficient cash: need $${cost.toFixed(2)}, have $${state.cash.toFixed(2)}` };
    }
    state.cash -= cost;
    const newQty = (held?.quantity ?? 0) + qty;
    const newCost = ((held?.quantity ?? 0) * (held?.avg_cost ?? 0) + cost) / newQty;
    state.positions.set(symbol, { quantity: newQty, avg_cost: newCost });
  } else {
    if (!held || held.quantity < qty) {
      return { error: `Insufficient shares: hold ${held?.quantity ?? 0}, tried to sell ${qty}` };
    }
    state.cash += qty * price;
    const remaining = held.quantity - qty;
    if (remaining <= 1e-9) state.positions.delete(symbol);
    else state.positions.set(symbol, { ...held, quantity: remaining });
  }

  state.snapshots.push({
    total_value: state.cash + positionsValue(),
    recorded_at: new Date().toISOString(),
  });
  return { id: randomUUID(), ticker: symbol, side, quantity: qty, price };
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const path = url.pathname;

  if (path === "/api/health") return send(res, 200, { status: "ok" });

  if (path === "/api/stream/prices") {
    // `no-transform` stops Next's dev rewrite proxy from gzipping the stream,
    // which would buffer it and leave the browser's EventSource silent.
    res.writeHead(200, {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    });
    const push = setInterval(() => {
      for (const ticker of activeTickers()) {
        const { price, previous } = state.prices.get(ticker);
        const change = price - previous;
        res.write(
          `data: ${JSON.stringify({
            ticker,
            price,
            previous_price: previous,
            change,
            direction: change > 0 ? "up" : change < 0 ? "down" : "flat",
            timestamp: new Date().toISOString(),
          })}\n\n`,
        );
      }
    }, 500);
    req.on("close", () => clearInterval(push));
    return;
  }

  if (path === "/api/portfolio" && req.method === "GET") return send(res, 200, portfolio());
  if (path === "/api/portfolio/history") return send(res, 200, state.snapshots);

  if (path === "/api/portfolio/trade" && req.method === "POST") {
    const result = applyTrade(await readBody(req));
    return result.error ? send(res, 400, { detail: result.error }) : send(res, 200, result);
  }

  if (path === "/api/watchlist" && req.method === "GET") {
    return send(
      res,
      200,
      state.watchlist.map((ticker) => {
        const entry = state.prices.get(ticker);
        const base = SEED[ticker] ?? entry?.price;
        return {
          ticker,
          price: entry?.price ?? null,
          previous_price: entry?.previous ?? null,
          change_percent: entry && base ? ((entry.price - base) / base) * 100 : null,
        };
      }),
    );
  }

  if (path === "/api/watchlist" && req.method === "POST") {
    const { ticker } = await readBody(req);
    const symbol = String(ticker ?? "").toUpperCase();
    if (!symbol) return send(res, 400, { detail: "Ticker is required" });
    if (state.watchlist.includes(symbol)) return send(res, 400, { detail: `${symbol} is already on the watchlist` });
    state.watchlist.push(symbol);
    if (!state.prices.has(symbol)) state.prices.set(symbol, { price: 100, previous: 100 });
    return send(res, 200, { ticker: symbol });
  }

  if (path.startsWith("/api/watchlist/") && req.method === "DELETE") {
    const symbol = decodeURIComponent(path.split("/").pop()).toUpperCase();
    state.watchlist = state.watchlist.filter((t) => t !== symbol);
    return send(res, 200, { ticker: symbol });
  }

  if (path === "/api/chat" && req.method === "POST") {
    const { message = "" } = await readBody(req);
    await new Promise((r) => setTimeout(r, 700));
    const trades = [];
    const match = /(buy|sell)\s+([\d.]+)\s+([A-Za-z]+)/i.exec(message);
    if (match) {
      const [, side, qty, ticker] = match;
      const result = applyTrade({ ticker, quantity: Number(qty), side: side.toLowerCase() });
      trades.push(
        result.error
          ? { ticker: ticker.toUpperCase(), side: side.toLowerCase(), quantity: Number(qty), status: "rejected", error: result.error }
          : { ...result, status: "filled" },
      );
    }
    return send(res, 200, {
      message: trades.length
        ? `Done. ${trades[0].status === "filled" ? "Order filled" : "Order rejected"} — ${trades[0].ticker}.`
        : `Mock assistant: your portfolio is worth $${(state.cash + positionsValue()).toFixed(2)} across ${state.positions.size} positions. Ask me to "buy 5 AAPL" to see a trade execute.`,
      trades,
      watchlist_changes: [],
    });
  }

  send(res, 404, { detail: "Not found" });
});

server.listen(PORT, () => console.log(`Mock FinAlly API listening on http://127.0.0.1:${PORT}`));
