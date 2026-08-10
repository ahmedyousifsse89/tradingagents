"use client";

import { Position, money } from "@/lib/api";

export function PositionsPanel({
  positions,
  equity,
}: {
  positions: Position[];
  equity: number | null | undefined;
}) {
  return (
    <section className="panel">
      <h2>Positions</h2>
      {positions.length === 0 ? (
        <p className="muted">Flat — no open positions.</p>
      ) : (
        <div className="scroll-x">
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th className="num">Qty</th>
                <th className="num">Price</th>
                <th className="num">Value</th>
                <th className="num">Weight</th>
                <th className="num">Unrealised</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((position) => (
                <tr key={position.symbol}>
                  <td>{position.symbol}</td>
                  <td className="num">{position.qty}</td>
                  <td className="num">{money(position.current_price)}</td>
                  <td className="num">{money(position.market_value)}</td>
                  <td className="num">
                    {equity ? `${((position.market_value / equity) * 100).toFixed(1)}%` : "—"}
                  </td>
                  <td
                    className="num"
                    style={{
                      color:
                        position.unrealized_pl > 0
                          ? "var(--green)"
                          : position.unrealized_pl < 0
                            ? "var(--red)"
                            : undefined,
                    }}
                  >
                    {money(position.unrealized_pl)}
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
