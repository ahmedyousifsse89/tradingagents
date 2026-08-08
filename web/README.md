# TradingAgents Dashboard

Next.js control panel for the TradingAgents execution bot. Deploys to Vercel;
talks to the bot's FastAPI control API running on Railway.

## Why a proxy instead of calling the API directly

Every request from the browser goes to a same-origin route under
`/api/proxy/*`, which runs on the server, verifies the session cookie, and
attaches the bot's bearer token. The token is a server-only environment
variable, so it never appears in the client bundle, in devtools, or in a
browser extension's reach. That also means there is no CORS configuration to
get wrong — the browser only ever talks to its own origin.

Sign-in is a single shared password, checked in constant time, exchanged for
an HMAC-signed session cookie that expires after 12 hours.

## Environment variables

All four are server-side. None are `NEXT_PUBLIC_`.

| Variable | Purpose |
|---|---|
| `TRADINGAGENTS_API_URL` | Railway service URL, no trailing slash |
| `TRADINGAGENTS_API_TOKEN` | Must match the token set on Railway |
| `DASHBOARD_PASSWORD` | Login password, minimum 8 characters |
| `SESSION_SECRET` | Signs the session cookie, minimum 24 characters |

Generate the secrets:

```bash
openssl rand -base64 32   # SESSION_SECRET
openssl rand -base64 32   # TRADINGAGENTS_API_TOKEN (use the same value on Railway)
```

## Local development

```bash
cp .env.example .env.local   # fill in the four variables
npm install
npm run dev                  # http://localhost:3000
```

Point `TRADINGAGENTS_API_URL` at `http://localhost:8000` and run the backend
with `docker compose --profile server up` to work against a local bot.

## Deploying to Vercel

1. Import the repository, set **Root Directory** to `web`.
2. Add the four environment variables above for Production (and Preview if you
   want preview deploys to work — note they will control the *same* bot).
3. Deploy. The framework preset, build command, and output are detected
   automatically.

## What the dashboard shows

- **Status** — which of the four money gates are open, account equity and
  cash, market open/closed, next scheduled run.
- **Kill switch** — high-water mark, current total and daily drawdown against
  their limits, halt/resume, and flatten-all behind a confirmation.
- **Watchlist** — add and remove tickers, trigger a run on demand.
- **Positions** — quantity, value, weight, unrealised P&L per name.
- **Runs** — every pass with its ratings, resulting orders, per-ticker errors,
  and the full Portfolio Manager decision text.
- **Order journal** — every intent recorded by the bot, including the ones
  that were rejected or dry-run.

State polls every 10 seconds.
