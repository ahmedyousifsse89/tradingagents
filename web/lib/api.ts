"use client";

/** Typed client for the same-origin proxy routes. */

export type Status = {
  runner: {
    running: boolean;
    running_run_id: string | null;
    watchlist: string[];
    schedule_enabled: boolean;
    schedule_cron: string;
    schedule_timezone: string;
    execution_enabled: boolean;
    execution_dry_run: boolean;
    alpaca_live: boolean;
    max_tickers: number;
  };
  risk: RiskStatus | null;
  scheduler: { running: boolean; next_run_time: string | null };
  account: {
    equity: number;
    cash: number;
    buying_power: number;
    trading_blocked: boolean;
    market_open: boolean;
  } | null;
  broker_error: string | null;
};

export type RiskStatus = {
  halted: boolean;
  halt_reason: string;
  halt_detail: string;
  halted_at: string;
  equity: number;
  high_water_mark: number;
  day_open_equity: number;
  total_drawdown: number;
  daily_drawdown: number;
  max_total_drawdown: number | null;
  max_daily_drawdown: number | null;
};

export type Position = {
  symbol: string;
  qty: number;
  market_value: number;
  current_price: number;
  avg_entry_price: number;
  unrealized_pl: number;
};

export type Order = {
  symbol: string;
  side: string;
  notional: number | null;
  qty: number | null;
  rating: string;
  trade_date: string;
  status: string;
  submitted: boolean;
  detail: string;
  reason: string;
  logged_at: string;
};

export type Run = {
  run_id: string;
  trigger: string;
  trade_date: string;
  started_at: string;
  finished_at: string;
  status: string;
  tickers: string[];
  ratings: Record<string, string>;
  decisions: Record<string, string>;
  orders: Order[];
  errors: Record<string, string>;
  note: string;
};

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/proxy/${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });

  const text = await response.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = { detail: text };
  }

  if (!response.ok) {
    if (response.status === 401) {
      // Session expired underneath a long-open tab.
      window.location.href = "/login";
    }
    const detail =
      (body as { detail?: string })?.detail ?? `request failed (${response.status})`;
    throw new ApiError(detail, response.status);
  }
  return body as T;
}

export const api = {
  status: () => call<Status>("status"),
  positions: () => call<{ positions: Position[] }>("positions"),
  watchlist: () => call<{ tickers: string[] }>("watchlist"),
  saveWatchlist: (tickers: string[]) =>
    call<{ tickers: string[] }>("watchlist", {
      method: "PUT",
      body: JSON.stringify({ tickers }),
    }),
  removeTicker: (ticker: string) =>
    call<{ tickers: string[] }>(`watchlist/${encodeURIComponent(ticker)}`, {
      method: "DELETE",
    }),
  runs: (limit = 25) => call<{ runs: Run[] }>(`runs?limit=${limit}`),
  triggerRun: (tickers?: string[]) =>
    call<{ accepted: boolean }>("runs", {
      method: "POST",
      body: JSON.stringify(tickers?.length ? { tickers } : {}),
    }),
  orders: (limit = 100) => call<{ orders: Order[] }>(`orders?limit=${limit}`),
  halt: (detail: string) =>
    call<RiskStatus>("risk/halt", { method: "POST", body: JSON.stringify({ detail }) }),
  resume: () => call<RiskStatus>("risk/resume", { method: "POST" }),
  flatten: () =>
    call<{ orders: Order[] }>("flatten", {
      method: "POST",
      body: JSON.stringify({ confirm: "FLATTEN" }),
    }),
};

export const money = (value: number | null | undefined) =>
  value == null
    ? "—"
    : value.toLocaleString(undefined, {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 2,
      });

export const percent = (value: number | null | undefined) =>
  value == null ? "—" : `${(value * 100).toFixed(2)}%`;

export const timestamp = (value: string | null | undefined) =>
  value ? new Date(value).toLocaleString() : "—";
