"use client";

import { useState } from "react";

import { RiskStatus, api, money, percent, timestamp } from "@/lib/api";

export function KillSwitchPanel({
  risk,
  onChange,
}: {
  risk: RiskStatus | null;
  onChange: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirmFlatten, setConfirmFlatten] = useState(false);

  async function act(action: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await action();
      onChange();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!risk) {
    return (
      <section className="panel">
        <h2>Kill switch</h2>
        <p className="muted">Disabled in configuration.</p>
      </section>
    );
  }

  return (
    <section className="panel">
      <h2>Kill switch</h2>

      {risk.halted ? (
        <div style={{ marginBottom: 12 }}>
          <span className="badge red">Halted</span>
          <p style={{ marginTop: 8 }}>{risk.halt_detail}</p>
          <p className="muted" style={{ fontSize: 12 }}>
            Tripped {timestamp(risk.halted_at)} ({risk.halt_reason})
          </p>
        </div>
      ) : (
        <p style={{ marginBottom: 12 }}>
          <span className="badge green">Armed</span>
        </p>
      )}

      <div className="stat-row">
        <div className="stat">
          <div className="label">High-water mark</div>
          <div className="value">{money(risk.high_water_mark)}</div>
        </div>
        <div className="stat">
          <div className="label">
            Total drawdown{risk.max_total_drawdown != null ? ` / ${percent(risk.max_total_drawdown)}` : ""}
          </div>
          <div className="value">{percent(risk.total_drawdown)}</div>
        </div>
        <div className="stat">
          <div className="label">
            Daily drawdown{risk.max_daily_drawdown != null ? ` / ${percent(risk.max_daily_drawdown)}` : ""}
          </div>
          <div className="value">{percent(risk.daily_drawdown)}</div>
        </div>
      </div>

      <div className="row" style={{ marginTop: 14 }}>
        {risk.halted ? (
          <button
            className="primary"
            disabled={busy}
            onClick={() => act(() => api.resume())}
          >
            Resume trading
          </button>
        ) : (
          <button
            className="danger"
            disabled={busy}
            onClick={() => act(() => api.halt("halted from the dashboard"))}
          >
            Halt trading
          </button>
        )}

        {confirmFlatten ? (
          <>
            <span className="muted">Sell every position at market?</span>
            <button
              className="danger"
              disabled={busy}
              onClick={() =>
                act(async () => {
                  await api.flatten();
                  setConfirmFlatten(false);
                })
              }
            >
              Yes, flatten
            </button>
            <button disabled={busy} onClick={() => setConfirmFlatten(false)}>
              Cancel
            </button>
          </>
        ) : (
          <button disabled={busy} onClick={() => setConfirmFlatten(true)}>
            Flatten all positions
          </button>
        )}
      </div>

      <p className="muted" style={{ fontSize: 12, marginTop: 10, marginBottom: 0 }}>
        Resuming rebases the high-water mark to current equity so the switch does
        not immediately re-trip on the same drawdown.
      </p>

      {error ? <div className="error">{error}</div> : null}
    </section>
  );
}
