"use client";

import { useCallback, useEffect, useState } from "react";

import { KillSwitchPanel } from "@/components/KillSwitchPanel";
import { OrdersPanel } from "@/components/OrdersPanel";
import { PositionsPanel } from "@/components/PositionsPanel";
import { RunsPanel } from "@/components/RunsPanel";
import { StatusPanel } from "@/components/StatusPanel";
import { WatchlistPanel } from "@/components/WatchlistPanel";
import { Order, Position, Run, Status, api } from "@/lib/api";

// Polled rather than pushed: a run takes minutes and the interesting state
// changes are coarse, so a websocket would buy nothing but complexity.
const POLL_MS = 10_000;

export default function DashboardPage() {
  const [status, setStatus] = useState<Status | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [statusBody, runsBody, ordersBody] = await Promise.all([
        api.status(),
        api.runs(25),
        api.orders(100),
      ]);
      setStatus(statusBody);
      setRuns(runsBody.runs);
      setOrders(ordersBody.orders);
      setError("");

      // Positions need a live broker; skip the call when status already says
      // the broker is down, so one outage does not produce two error banners.
      if (statusBody.broker_error) {
        setPositions([]);
      } else {
        setPositions((await api.positions()).positions);
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), POLL_MS);
    return () => clearInterval(timer);
  }, [refresh]);

  async function signOut() {
    await fetch("/api/auth/logout", { method: "POST" });
    window.location.href = "/login";
  }

  return (
    <main className="shell">
      <header className="top">
        <h1>TradingAgents Control</h1>
        <div className="row">
          <button onClick={() => void refresh()}>Refresh</button>
          <button onClick={signOut}>Sign out</button>
        </div>
      </header>

      {error ? <div className="panel error">{error}</div> : null}
      {!loaded ? <p className="muted">Loading…</p> : null}

      <div className="grid">
        <StatusPanel status={status} />
        <KillSwitchPanel risk={status?.risk ?? null} onChange={() => void refresh()} />
        <WatchlistPanel
          tickers={status?.runner.watchlist ?? []}
          running={Boolean(status?.runner.running)}
          onChange={() => void refresh()}
        />
        <PositionsPanel positions={positions} equity={status?.account?.equity} />
        <RunsPanel runs={runs} />
        <OrdersPanel orders={orders} />
      </div>
    </main>
  );
}
