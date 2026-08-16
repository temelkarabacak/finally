"use client";

import { useState } from "react";
import { ChatPanel } from "@/components/ChatPanel";
import { Header } from "@/components/Header";
import { Heatmap } from "@/components/Heatmap";
import { PnlChart } from "@/components/PnlChart";
import { PositionsTable } from "@/components/PositionsTable";
import { PriceChart } from "@/components/PriceChart";
import { StatusBar } from "@/components/StatusBar";
import { TradeBar } from "@/components/TradeBar";
import { Watchlist } from "@/components/Watchlist";
import { TerminalProvider } from "@/hooks/useTerminal";

export default function Page() {
  const [chatOpen, setChatOpen] = useState(true);

  return (
    <TerminalProvider>
      <div className="flex h-screen flex-col overflow-hidden">
        <Header />

        <main
          className="grid min-h-0 flex-1 gap-1 p-1"
          style={{ gridTemplateColumns: `280px minmax(0, 1fr) ${chatOpen ? "360px" : "auto"}` }}
        >
          <Watchlist />

          <div className="grid min-h-0 min-w-0 gap-1" style={{ gridTemplateRows: "1.15fr 1fr 1fr auto" }}>
            <PriceChart />
            <div className="grid min-h-0 gap-1" style={{ gridTemplateColumns: "1fr 1fr" }}>
              <PnlChart />
              <Heatmap />
            </div>
            <PositionsTable />
            <TradeBar />
          </div>

          {chatOpen ? (
            <ChatPanel onCollapse={() => setChatOpen(false)} />
          ) : (
            <button
              type="button"
              aria-label="Open chat"
              onClick={() => setChatOpen(true)}
              className="flex w-8 flex-col items-center gap-3 rounded-sm border border-edge bg-panel py-3 text-ink-dim transition-colors hover:border-blue hover:text-blue"
            >
              <span aria-hidden="true">‹</span>
              <span className="panel-label [writing-mode:vertical-rl] text-[10px]">AI Copilot</span>
            </button>
          )}
        </main>

        <StatusBar />
      </div>
    </TerminalProvider>
  );
}
