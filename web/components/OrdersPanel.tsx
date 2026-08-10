"use client";

import { Order, money, timestamp } from "@/lib/api";

const STATUS_CLASS: Record<string, string> = {
  submitted: "green",
  dry_run: "grey",
  rejected: "amber",
  duplicate: "grey",
  error: "red",
};

export function OrderStatus({ status }: { status: string }) {
  return <span className={`badge ${STATUS_CLASS[status] ?? "grey"}`}>{status}</span>;
}

export function orderSize(order: Order) {
  if (order.notional != null) return money(order.notional);
  if (order.qty != null) return `${order.qty} sh`;
  return "—";
}

export function OrdersPanel({ orders }: { orders: Order[] }) {
  return (
    <section className="panel wide">
      <h2>Order journal</h2>
      {orders.length === 0 ? (
        <p className="muted">
          Nothing yet. Every intent is recorded here — submitted, rejected, or dry-run.
        </p>
      ) : (
        <div className="scroll-x">
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Status</th>
                <th>Side</th>
                <th>Symbol</th>
                <th className="num">Size</th>
                <th>Rating</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order, index) => (
                <tr key={`${order.logged_at}-${order.symbol}-${index}`}>
                  <td>{timestamp(order.logged_at)}</td>
                  <td>
                    <OrderStatus status={order.status} />
                  </td>
                  <td>{order.side?.toUpperCase()}</td>
                  <td>{order.symbol}</td>
                  <td className="num">{orderSize(order)}</td>
                  <td>{order.rating}</td>
                  <td style={{ whiteSpace: "normal", minWidth: 260 }}>
                    {order.detail || order.reason}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
