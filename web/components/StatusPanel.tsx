"use client";

import { Status, money, timestamp } from "@/lib/api";

/** Which of the four money gates are open, rendered as the headline fact. */
function ModeBadge({ status }: { status: Status }) {
  const { execution_enabled, execution_dry_run, alpaca_live } = status.runner;

  if (!execution_enabled || execution_dry_run) {
    return <span className="badge grey">Dry run — no orders sent</span>;
  }
  if (alpaca_live) {
    return <span className="badge red">LIVE — real money</span>;
  }
  return <span className="badge amber">Paper trading</span>;
}

export function StatusPanel({ status }: { status: Status | null }) {
  if (!status) {
    return (
      <section className="panel">
        <h2>Status</h2>
        <p className="muted">Loading…</p>
      </section>
    );
  }

  const account = status.account;

  return (
    <section className="panel">
      <h2>Status</h2>
      <div className="row" style={{ marginBottom: 12 }}>
        <ModeBadge status={status} />
        {status.risk?.halted ? (
          <span className="badge red">Halted</span>
        ) : (
          <span className="badge green">Trading allowed</span>
        )}
        {status.runner.running ? (
          <span className="badge amber">Run in progress</span>
        ) : null}
        {account?.market_open ? (
          <span className="badge green">Market open</span>
        ) : (
          <span className="badge grey">Market closed</span>
        )}
      </div>

      {status.broker_error ? (
        <p className="error">Broker unreachable: {status.broker_error}</p>
      ) : (
        <div className="stat-row">
          <div className="stat">
            <div className="label">Equity</div>
            <div className="value">{money(account?.equity)}</div>
          </div>
          <div className="stat">
            <div className="label">Cash</div>
            <div className="value">{money(account?.cash)}</div>
          </div>
          <div className="stat">
            <div className="label">Buying power</div>
            <div className="value">{money(account?.buying_power)}</div>
          </div>
        </div>
      )}

      <div className="muted" style={{ marginTop: 12, fontSize: 12 }}>
        <div>
          Schedule:{" "}
          {status.runner.schedule_enabled ? (
            <>
              <code>{status.runner.schedule_cron}</code> ({status.runner.schedule_timezone})
              {" · next "}
              {timestamp(status.scheduler.next_run_time)}
            </>
          ) : (
            "disabled"
          )}
        </div>
        <div>Max tickers per run: {status.runner.max_tickers}</div>
      </div>
    </section>
  );
}
