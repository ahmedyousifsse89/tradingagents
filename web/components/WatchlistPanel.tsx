"use client";

import { useState } from "react";

import { api } from "@/lib/api";

export function WatchlistPanel({
  tickers,
  running,
  onChange,
}: {
  tickers: string[];
  running: boolean;
  onChange: () => void;
}) {
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function act(action: () => Promise<unknown>, message = "") {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      if (message) setNotice(message);
      onChange();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function add(event: React.FormEvent) {
    event.preventDefault();
    const candidate = draft.trim().toUpperCase();
    if (!candidate) return;
    if (tickers.includes(candidate)) {
      setDraft("");
      return;
    }
    void act(async () => {
      await api.saveWatchlist([...tickers, candidate]);
      setDraft("");
    });
  }

  return (
    <section className="panel">
      <h2>Watchlist</h2>

      <form onSubmit={add} className="row" style={{ marginBottom: 12 }}>
        <input
          type="text"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Add ticker, e.g. NVDA"
          style={{ flex: "1 1 160px" }}
        />
        <button type="submit" disabled={busy || !draft.trim()}>
          Add
        </button>
      </form>

      {tickers.length === 0 ? (
        <p className="muted">Empty — scheduled runs will do nothing.</p>
      ) : (
        <div className="row">
          {tickers.map((ticker) => (
            <span key={ticker} className="chip">
              {ticker}
              <button
                type="button"
                aria-label={`Remove ${ticker}`}
                disabled={busy}
                onClick={() => act(() => api.removeTicker(ticker))}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="row" style={{ marginTop: 16 }}>
        <button
          className="primary"
          disabled={busy || running || tickers.length === 0}
          onClick={() =>
            act(() => api.triggerRun(), "Run started. Results appear below as each ticker finishes.")
          }
        >
          {running ? "Run in progress…" : "Run now"}
        </button>
        <span className="muted" style={{ fontSize: 12 }}>
          A full pass is many LLM calls per ticker and takes minutes.
        </span>
      </div>

      {notice ? (
        <p className="muted" style={{ marginBottom: 0 }}>
          {notice}
        </p>
      ) : null}
      {error ? <div className="error">{error}</div> : null}
    </section>
  );
}
