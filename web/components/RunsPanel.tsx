"use client";

import { Run, timestamp } from "@/lib/api";
import { OrderStatus, orderSize } from "./OrdersPanel";

const RUN_STATUS_CLASS: Record<string, string> = {
  completed: "green",
  running: "amber",
  halted: "red",
  failed: "red",
};

function RatingBadge({ rating }: { rating: string }) {
  const tone =
    rating === "Buy" || rating === "Overweight"
      ? "green"
      : rating === "Sell" || rating === "Underweight"
        ? "red"
        : "grey";
  return <span className={`badge ${tone}`}>{rating}</span>;
}

function RunDetail({ run }: { run: Run }) {
  return (
    <div style={{ padding: "8px 0 4px" }}>
      {run.note ? (
        <p className="muted" style={{ marginTop: 0 }}>
          {run.note}
        </p>
      ) : null}

      {Object.entries(run.errors).map(([ticker, message]) => (
        <p key={ticker} className="error">
          {ticker}: {message}
        </p>
      ))}

      {run.orders.length > 0 ? (
        <div className="scroll-x" style={{ marginBottom: 12 }}>
          <table>
            <thead>
              <tr>
                <th>Status</th>
                <th>Side</th>
                <th>Symbol</th>
                <th className="num">Size</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              {run.orders.map((order, index) => (
                <tr key={`${order.symbol}-${index}`}>
                  <td>
                    <OrderStatus status={order.status} />
                  </td>
                  <td>{order.side?.toUpperCase()}</td>
                  <td>{order.symbol}</td>
                  <td className="num">{orderSize(order)}</td>
                  <td style={{ whiteSpace: "normal", minWidth: 240 }}>
                    {order.detail || order.reason}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {Object.entries(run.decisions).map(([ticker, decision]) => (
        <details key={ticker}>
          <summary>
            {ticker} — Portfolio Manager decision{" "}
            <RatingBadge rating={run.ratings[ticker] ?? "?"} />
          </summary>
          <pre className="decision">{decision}</pre>
        </details>
      ))}
    </div>
  );
}

export function RunsPanel({ runs }: { runs: Run[] }) {
  return (
    <section className="panel wide">
      <h2>Runs</h2>
      {runs.length === 0 ? (
        <p className="muted">No runs yet.</p>
      ) : (
        runs.map((run) => (
          <details key={run.run_id} style={{ borderBottom: "1px solid var(--border)" }}>
            <summary>
              <span className={`badge ${RUN_STATUS_CLASS[run.status] ?? "grey"}`}>
                {run.status}
              </span>{" "}
              <strong>{run.trade_date}</strong>{" "}
              <span className="muted">
                {run.trigger} · {timestamp(run.started_at)} ·{" "}
                {run.tickers.join(", ") || "no tickers"}
              </span>{" "}
              {Object.entries(run.ratings).map(([ticker, rating]) => (
                <span key={ticker} style={{ marginLeft: 6 }}>
                  <RatingBadge rating={rating} />
                </span>
              ))}
            </summary>
            <RunDetail run={run} />
          </details>
        ))
      )}
    </section>
  );
}
