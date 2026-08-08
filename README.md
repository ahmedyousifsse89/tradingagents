<p align="center">
  <img src="assets/TauricResearch.png" style="width: 60%; height: auto;">
</p>

<div align="center" style="line-height: 1;">
  <a href="https://arxiv.org/abs/2412.20138" target="_blank"><img alt="arXiv" src="https://img.shields.io/badge/arXiv-2412.20138-B31B1B?logo=arxiv"/></a>
  <a href="https://discord.com/invite/hk9PGKShPK" target="_blank"><img alt="Discord" src="https://img.shields.io/badge/Discord-TradingResearch-7289da?logo=discord&logoColor=white&color=7289da"/></a>
  <a href="./assets/wechat.png" target="_blank"><img alt="WeChat" src="https://img.shields.io/badge/WeChat-TauricResearch-brightgreen?logo=wechat&logoColor=white"/></a>
  <a href="https://x.com/TauricResearch" target="_blank"><img alt="X Follow" src="https://img.shields.io/badge/X-TauricResearch-white?logo=x&logoColor=white"/></a>
  <br>
  <a href="https://github.com/TauricResearch/" target="_blank"><img alt="Community" src="https://img.shields.io/badge/Join_GitHub_Community-TauricResearch-14C290?logo=discourse"/></a>
</div>

<div align="center">
  <!-- Keep these links. Translations will automatically update with the README. -->
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=de">Deutsch</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=es">Español</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=fr">français</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ja">日本語</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ko">한국어</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=pt">Português</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ru">Русский</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=zh">中文</a>
</div>

---

# TradingAgents: Multi-Agents LLM Financial Trading Framework

## News
- [2026-05] **TradingAgents v0.2.5** released with the grounded Sentiment Analyst, GPT-5.5 etc. model coverage, Qwen/GLM/MiniMax dual-region support, `TRADINGAGENTS_*` env-var configurability with API-key auto-detection, remote Ollama support, non-US alpha benchmarks, and ticker path-traversal hardening. See [CHANGELOG.md](CHANGELOG.md) for the full list.
- [2026-04] **TradingAgents v0.2.4** released with structured-output agents (Research Manager, Trader, Portfolio Manager), LangGraph checkpoint resume, persistent decision log, DeepSeek/Qwen/GLM/Azure provider support, Docker, and a Windows UTF-8 encoding fix.
- [2026-03] **TradingAgents v0.2.3** released with multi-language support, GPT-5.4 family models, unified model catalog, backtesting date fidelity, and proxy support.
- [2026-03] **TradingAgents v0.2.2** released with GPT-5.4/Gemini 3.1/Claude 4.6 model coverage, five-tier rating scale, OpenAI Responses API, Anthropic effort control, and cross-platform stability.
- [2026-02] **TradingAgents v0.2.0** released with multi-provider LLM support (GPT-5.x, Gemini 3.x, Claude 4.x, Grok 4.x) and improved system architecture.
- [2026-01] **Trading-R1** [Technical Report](https://arxiv.org/abs/2509.11420) released, with [Terminal](https://github.com/TauricResearch/Trading-R1) expected to land soon.

<div align="center">
<a href="https://www.star-history.com/#TauricResearch/TradingAgents&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=TauricResearch/TradingAgents&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=TauricResearch/TradingAgents&type=Date" />
   <img alt="TradingAgents Star History" src="https://api.star-history.com/svg?repos=TauricResearch/TradingAgents&type=Date" style="width: 80%; height: auto;" />
 </picture>
</a>
</div>

> 🎉 **TradingAgents** officially released! We have received numerous inquiries about the work, and we would like to express our thanks for the enthusiasm in our community.
>
> So we decided to fully open-source the framework. Looking forward to building impactful projects with you!

<div align="center">

🚀 [TradingAgents](#tradingagents-framework) | ⚡ [Installation & CLI](#installation-and-cli) | 🎬 [Demo](https://www.youtube.com/watch?v=90gr5lwjIho) | 📦 [Package Usage](#tradingagents-package) | 🤝 [Contributing](#contributing) | 📄 [Citation](#citation)

</div>

## TradingAgents Framework

TradingAgents is a multi-agent trading framework that mirrors the dynamics of real-world trading firms. By deploying specialized LLM-powered agents: from fundamental analysts, sentiment experts, and technical analysts, to trader, risk management team, the platform collaboratively evaluates market conditions and informs trading decisions. Moreover, these agents engage in dynamic discussions to pinpoint the optimal strategy.

<p align="center">
  <img src="assets/schema.png" style="width: 100%; height: auto;">
</p>

> TradingAgents framework is designed for research purposes. Trading performance may vary based on many factors, including the chosen backbone language models, model temperature, trading periods, the quality of data, and other non-deterministic factors. [It is not intended as financial, investment, or trading advice.](https://tauric.ai/disclaimer/)

Our framework decomposes complex trading tasks into specialized roles. This ensures the system achieves a robust, scalable approach to market analysis and decision-making.

### Analyst Team
- Fundamentals Analyst: Evaluates company financials and performance metrics, identifying intrinsic values and potential red flags.
- Sentiment Analyst: Aggregates news headlines, StockTwits, and Reddit chatter into a single sentiment read to gauge short-term market mood.
- News Analyst: Monitors global news and macroeconomic indicators, interpreting the impact of events on market conditions.
- Technical Analyst: Utilizes technical indicators (like MACD and RSI) to detect trading patterns and forecast price movements.

<p align="center">
  <img src="assets/analyst.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

### Researcher Team
- Comprises both bullish and bearish researchers who critically assess the insights provided by the Analyst Team. Through structured debates, they balance potential gains against inherent risks.

<p align="center">
  <img src="assets/researcher.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

### Trader Agent
- Composes reports from the analysts and researchers to make informed trading decisions. It determines the timing and magnitude of trades based on comprehensive market insights.

<p align="center">
  <img src="assets/trader.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

### Risk Management and Portfolio Manager
- Continuously evaluates portfolio risk by assessing market volatility, liquidity, and other risk factors. The risk management team evaluates and adjusts trading strategies, providing assessment reports to the Portfolio Manager for final decision.
- The Portfolio Manager approves/rejects the transaction proposal. If approved, the order will be sent to the simulated exchange and executed.

<p align="center">
  <img src="assets/risk.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

## Installation and CLI

### Installation

Clone TradingAgents:
```bash
git clone https://github.com/TauricResearch/TradingAgents.git
cd TradingAgents
```

Create a virtual environment in any of your favorite environment managers:
```bash
conda create -n tradingagents python=3.13
conda activate tradingagents
```

Install the package and its dependencies:
```bash
pip install .
```

### Docker

Alternatively, run with Docker:
```bash
cp .env.example .env  # add your API keys
docker compose run --rm tradingagents
```

For local models with Ollama:
```bash
docker compose --profile ollama run --rm tradingagents-ollama
```

### Required APIs

TradingAgents supports multiple LLM providers. Set the API key for your chosen provider:

```bash
export OPENAI_API_KEY=...          # OpenAI (GPT)
export GOOGLE_API_KEY=...          # Google (Gemini)
export ANTHROPIC_API_KEY=...       # Anthropic (Claude)
export XAI_API_KEY=...             # xAI (Grok)
export DEEPSEEK_API_KEY=...        # DeepSeek
export DASHSCOPE_API_KEY=...       # Qwen — International (dashscope-intl.aliyuncs.com)
export DASHSCOPE_CN_API_KEY=...    # Qwen — China (dashscope.aliyuncs.com)
export ZHIPU_API_KEY=...           # GLM via Z.AI (international)
export ZHIPU_CN_API_KEY=...        # GLM via BigModel (China, open.bigmodel.cn)
export MINIMAX_API_KEY=...         # MiniMax — Global (api.minimax.io, M2.x, 204K ctx)
export MINIMAX_CN_API_KEY=...      # MiniMax — China (api.minimaxi.com, M2.x, 204K ctx)
export OPENROUTER_API_KEY=...      # OpenRouter
export ALPHA_VANTAGE_API_KEY=...   # Alpha Vantage
```

For enterprise providers (e.g. Azure OpenAI, AWS Bedrock), copy `.env.enterprise.example` to `.env.enterprise` and fill in your credentials.

For local models, configure Ollama with `llm_provider: "ollama"`. The default endpoint is `http://localhost:11434/v1`; set `OLLAMA_BASE_URL` to point at a remote `ollama-serve`. Pull models with `ollama pull <name>`, and pick "Custom model ID" in the CLI for any model not listed by default.

Alternatively, copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```

### CLI Usage

Launch the interactive CLI:
```bash
tradingagents          # installed command
python -m cli.main     # alternative: run directly from source
```
You will see a screen where you can select your desired tickers, analysis date, LLM provider, research depth, and more.

<p align="center">
  <img src="assets/cli/cli_init.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

An interface will appear showing results as they load, letting you track the agent's progress as it runs.

<p align="center">
  <img src="assets/cli/cli_news.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

<p align="center">
  <img src="assets/cli/cli_transaction.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

## TradingAgents Package

### Implementation Details

We built TradingAgents with LangGraph to ensure flexibility and modularity. The framework supports multiple LLM providers: OpenAI, Google, Anthropic, xAI, DeepSeek, Qwen (Alibaba DashScope, international and China endpoints), GLM (Zhipu), MiniMax (global + China), OpenRouter, Ollama for local models, and Azure OpenAI for enterprise.

### Python Usage

To use TradingAgents inside your code, you can import the `tradingagents` module and initialize a `TradingAgentsGraph()` object. The `.propagate()` function will return a decision. You can run `main.py`, here's also a quick example:

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

ta = TradingAgentsGraph(debug=True, config=DEFAULT_CONFIG.copy())

# forward propagate
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)
```

You can also adjust the default configuration to set your own choice of LLMs, debate rounds, etc.

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"        # openai, google, anthropic, xai, deepseek, qwen, qwen-cn, glm, glm-cn, minimax, minimax-cn, openrouter, ollama, azure
config["deep_think_llm"] = "gpt-5.4"     # Model for complex reasoning
config["quick_think_llm"] = "gpt-5.4-mini" # Model for quick tasks
config["max_debate_rounds"] = 2

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)
```

See `tradingagents/default_config.py` for all configuration options.

## Persistence and Recovery

TradingAgents persists two kinds of state across runs.

### Decision log

The decision log is always on. Each completed run appends its decision to `~/.tradingagents/memory/trading_memory.md`. On the next run for the same ticker, TradingAgents fetches the realised return (raw and alpha vs SPY), generates a one-paragraph reflection, and injects the most recent same-ticker decisions plus recent cross-ticker lessons into the Portfolio Manager prompt, so each analysis carries forward what worked and what didn't.

When a broker is attached, the realised return is measured from the price the
account **actually filled at**, not from the closing price on the analysis
date — so slippage and the gap between analysis and execution are part of what
the agents learn from. Decisions that never traded (a Hold, or an order a guard
rejected) are still graded, but the reflection prompt says the outcome is
hypothetical so no execution lessons are drawn from a trade nobody made.

Override the path with `TRADINGAGENTS_MEMORY_LOG_PATH`.

### Checkpoint resume

Checkpoint resume is opt-in via `--checkpoint`. When enabled, LangGraph saves state after each node so a crashed or interrupted run resumes from the last successful step instead of starting over. On a resume run you will see `Resuming from step N for <TICKER> on <date>` in the logs; on a new run you will see `Starting fresh`. Checkpoints are cleared automatically on successful completion.

Per-ticker SQLite databases live at `~/.tradingagents/cache/checkpoints/<TICKER>.db` (override the base with `TRADINGAGENTS_CACHE_DIR`). Use `--clear-checkpoints` to reset all of them before a run.

```bash
tradingagents analyze --checkpoint           # enable for this run
tradingagents analyze --clear-checkpoints    # reset before running
```

```python
config = DEFAULT_CONFIG.copy()
config["checkpoint_enabled"] = True
ta = TradingAgentsGraph(config=config)
_, decision = ta.propagate("NVDA", "2026-01-15")
```

## Broker Execution (Alpaca)

> **Trading real money is irreversible.** This layer can place live orders from
> LLM-derived ratings. Run it against Alpaca's paper endpoint until you have
> reviewed enough dry runs to trust the sizing, and treat every default below as
> a floor for caution rather than a recommendation. The framework remains
> research software and is [not financial, investment, or trading advice](https://tauric.ai/disclaimer/).

`tradingagents.execution` turns the 5-tier rating from `.propagate()` into
broker orders. Install the optional dependency:

```bash
pip install -e ".[execution]"
```

### How a rating becomes an order

1. **Sizing.** Each rating maps to a target fraction of account equity —
   Buy 8%, Overweight 4%, Hold (leave alone), Underweight 2%, Sell 0% by
   default. Sizes are computed arithmetically; the Trader agent's free-text
   `position_sizing` field is deliberately never parsed into share counts.
2. **Reconciliation.** The engine compares target value against the position
   Alpaca actually reports and orders only the difference. Re-running the same
   ticker and date after a fill therefore produces no orders instead of
   doubling the position.
3. **Guards.** Blocked accounts, closed markets, dust-sized rebalances,
   oversized orders, a daily order cap, and duplicate `client_order_id`s are
   all rejected before submission. The same guards run in dry-run mode, so a
   clean dry run is evidence about what a live run would do.
4. **Journal.** Every intent — submitted, rejected, or dry-run — is appended to
   `~/.tradingagents/cache/execution/journal.jsonl`.

### Four switches guard real money

Money can only move when **all** of these are set the permissive way:

| Switch | Default | Effect |
|---|---|---|
| `execution_enabled` | `False` | Master switch; submission raises without it |
| `execution_dry_run` | `True` | Plans and journals orders, never sends them |
| `alpaca_live` | `False` | Selects the live endpoint over paper |
| `TRADINGAGENTS_ALPACA_ALLOW_LIVE` | unset | Environment opt-in checked inside the broker |

Credentials come from `ALPACA_API_KEY_ID` and `ALPACA_API_SECRET_KEY`.

### Usage

```python
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.execution import ExecutionEngine, describe_results
from tradingagents.graph.trading_graph import TradingAgentsGraph

config = DEFAULT_CONFIG.copy()
ta = TradingAgentsGraph(config=config)
_, rating = ta.propagate("NVDA", "2026-01-15")   # e.g. "Buy"

# Dry run by default: plans and journals, submits nothing.
engine = ExecutionEngine(config)
results = engine.execute_decision("NVDA", rating, trade_date="2026-01-15")
print(describe_results(results))
```

Rate several tickers in one pass so the gross-exposure cap sees the whole book:

```python
ratings = {t: ta.propagate(t, "2026-01-15")[1] for t in ("NVDA", "AMD", "TSLA")}
results = engine.execute_ratings(ratings, trade_date="2026-01-15")
```

To submit against the **paper** account, set `execution_enabled=True` and
`execution_dry_run=False`, leaving `alpaca_live` at `False`.

Tune the caps in `default_config.py` or via `TRADINGAGENTS_MAX_POSITION_WEIGHT`,
`TRADINGAGENTS_MAX_GROSS_EXPOSURE`, `TRADINGAGENTS_MIN_ORDER_NOTIONAL`, and
`TRADINGAGENTS_MAX_ORDERS_PER_DAY`.

### Portfolio context

When a broker is passed to `TradingAgentsGraph(broker=...)`, live holdings,
cash, and exposure are rendered into the Trader and Portfolio Manager prompts.
The agents then know whether a name is already held, already at its cap, or not
held at all — so "Hold, already at target" becomes an informed answer rather
than a coincidence. This never affects order sizing; the reconciler owns that,
arithmetically, from broker data. A broker outage degrades the prompt to empty
rather than failing the run.

### Kill switch

The kill switch tracks an equity high-water mark and halts all trading when the
account falls too far below it. Every order is rejected while halted, in
dry-run mode too.

| Setting | Default | Meaning |
|---|---|---|
| `risk_kill_switch_enabled` | `True` | Master switch for drawdown protection |
| `risk_max_total_drawdown` | `0.15` | Halt at 15% below the all-time high-water mark |
| `risk_max_daily_drawdown` | `0.05` | Halt at 5% below the current UTC day's open |
| `risk_flatten_on_halt` | `False` | Whether a halt also liquidates every position |

With `risk_flatten_on_halt` on, liquidation happens on the transition — at run
start if the switch was already tripped, or the moment it trips mid-run, so an
intraday collapse does not wait for the next scheduled pass.

A tripped switch **never clears itself** — not on recovery, not on restart.
Resuming is a human action (dashboard button or `KillSwitch.resume()`), and it
rebases the high-water mark to current equity so the switch does not
immediately re-trip on the drawdown it was just cleared for. State lives in
`~/.tradingagents/cache/execution/risk_state.json`; a corrupt state file reads
as halted rather than as permission to trade.

## Running as a Bot

> Everything below turns the framework into software that trades while nobody
> is watching. Read the four switches above first, run in dry-run until the
> journal shows orders you would have placed yourself, then paper, then live.

`tradingagents.runner` adds unattended operation and `tradingagents.server`
adds the HTTP control plane the dashboard talks to:

```bash
pip install -e ".[server]"
```

### The run cycle

One pass does three things in order:

1. **Kill switch first.** A halted account skips analysis entirely, so a halt
   costs nothing in LLM spend.
2. **Analyse every ticker.** A ticker that raises is recorded in the run's
   `errors` and the pass continues — the other tickers have already been paid
   for. When the watchlist is longer than `run_max_tickers`, each pass takes
   the least recently analysed names, so the cap rotates coverage instead of
   permanently starving the tail.
3. **Execute once, as a batch.** All ratings go to the engine in a single call
   so the gross-exposure cap sees the whole book instead of approving each name
   in ignorance of the others.

Only one run happens at a time. A scheduled fire landing on a run in progress
is dropped, not queued: two concurrent passes would both read the same
pre-trade positions and each size orders as if the other had not happened.

```python
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.runner import TradingRunner

runner = TradingRunner(DEFAULT_CONFIG.copy())
runner.watchlist.save(["NVDA", "AMD", "TSLA"])
record = runner.run_once()
print(record.status, record.ratings)
```

### Scheduling

```bash
TRADINGAGENTS_SCHEDULE_ENABLED=true
TRADINGAGENTS_SCHEDULE_CRON="30 13 * * 1-5"   # 13:30 UTC weekdays, pre-US-open
TRADINGAGENTS_SCHEDULE_TIMEZONE=UTC
TRADINGAGENTS_RUN_MAX_TICKERS=10              # cost and duration cap per pass
```

Missed fires coalesce into one run rather than stampeding the broker after an
outage.

### Control API

`python -m tradingagents.server.main` serves the API and owns the scheduler
thread in the same process, so scheduled and API-triggered runs contend for the
same lock and can never overlap.

`TRADINGAGENTS_API_TOKEN` is required — the API can place trades and refuses to
start without it. Every route except `/health` needs `Authorization: Bearer …`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness probe, unauthenticated, exposes nothing |
| GET | `/api/status` | Mode, account, kill switch, next scheduled run |
| GET | `/api/positions` | Open positions with unrealised P&L |
| GET/PUT | `/api/watchlist` | Read or replace the watchlist |
| DELETE | `/api/watchlist/{ticker}` | Remove one ticker |
| GET/POST | `/api/runs` | Run history, or trigger a run (202; 409 if busy) |
| GET | `/api/runs/{run_id}` | One run with decisions and orders |
| GET | `/api/orders` | The order journal |
| GET | `/api/risk` | Kill-switch state |
| POST | `/api/risk/halt` · `/api/risk/resume` | Manual halt and resume |
| POST | `/api/flatten` | Close all positions; body must be `{"confirm":"FLATTEN"}` |

## Deploying

The bot runs on Railway; the dashboard runs on Vercel. They are separate
deploys sharing one secret.

### 1. Railway (the bot)

Deploy this repository — `railway.json` selects `Dockerfile.server` and health
checks `/health`.

**Attach a volume mounted at `/data`.** Without it the container filesystem is
ephemeral: the order journal, run history, watchlist, decision memory, and the
kill switch's high-water mark all reset on every redeploy, and a halted bot
would come back armed.

**Keep replicas at 1.** Each replica runs its own scheduler and its own
in-process lock, so two replicas means two runs per cron tick against one
account.

Set the service variables from [`.env.server.example`](.env.server.example). At
minimum: an LLM provider key, `TRADINGAGENTS_API_TOKEN`, `ALPACA_API_KEY_ID`,
and `ALPACA_API_SECRET_KEY`. Leave every execution gate at its default for the
first deploy.

```bash
python -c 'import secrets; print(secrets.token_urlsafe(32))'   # API token
```

### 2. Vercel (the dashboard)

Import the same repository with **Root Directory** set to `web`, then set the
four variables in [`web/.env.example`](web/.env.example):
`TRADINGAGENTS_API_URL` (the Railway URL), `TRADINGAGENTS_API_TOKEN` (identical
to Railway's), `DASHBOARD_PASSWORD`, and `SESSION_SECRET`.

None of them are `NEXT_PUBLIC_`. The browser calls same-origin proxy routes
that attach the bearer token server-side, so the token never reaches the client
and there is no CORS to configure. See [`web/README.md`](web/README.md).

### 3. Going live, in order

1. Deploy with the defaults. Add tickers, hit **Run now**, and read the journal
   — every intent is recorded with the size it would have used.
2. When the dry-run orders look like orders you would have placed, set
   `TRADINGAGENTS_EXECUTION_ENABLED=true` and
   `TRADINGAGENTS_EXECUTION_DRY_RUN=false`. This trades the **paper** account.
3. Turn on the scheduler and leave it on paper for as long as it takes to see
   it behave across a full cycle.
4. Only then set `TRADINGAGENTS_ALPACA_LIVE=true` **and**
   `TRADINGAGENTS_ALPACA_ALLOW_LIVE=true`. Both are required; either one alone
   keeps you on paper.

Running costs are dominated by LLM calls: one pass is a full multi-agent
analysis per ticker, so `TRADINGAGENTS_RUN_MAX_TICKERS` and the cron frequency
are your spend controls.

## Contributing

We welcome contributions from the community! Whether it's fixing a bug, improving documentation, or suggesting a new feature, your input helps make this project better. If you are interested in this line of research, please consider joining our open-source financial AI research community [Tauric Research](https://tauric.ai/).

Past contributions, including code, design feedback, and bug reports, are credited per release in [`CHANGELOG.md`](CHANGELOG.md).

## Citation

Please reference our work if you find *TradingAgents* provides you with some help :)

```
@misc{xiao2025tradingagentsmultiagentsllmfinancial,
      title={TradingAgents: Multi-Agents LLM Financial Trading Framework}, 
      author={Yijia Xiao and Edward Sun and Di Luo and Wei Wang},
      year={2025},
      eprint={2412.20138},
      archivePrefix={arXiv},
      primaryClass={q-fin.TR},
      url={https://arxiv.org/abs/2412.20138}, 
}
```
