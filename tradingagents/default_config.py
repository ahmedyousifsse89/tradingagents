import os

_TRADINGAGENTS_HOME = os.path.join(os.path.expanduser("~"), ".tradingagents")

# Single source of truth for env-var → config-key overrides. To expose
# a new config key for environment-based override, add a row here — no
# entry-point script changes required. Coercion is driven by the type
# of the existing default, so users can keep writing plain strings in
# their .env file.
_ENV_OVERRIDES = {
    "TRADINGAGENTS_LLM_PROVIDER":         "llm_provider",
    "TRADINGAGENTS_DEEP_THINK_LLM":       "deep_think_llm",
    "TRADINGAGENTS_QUICK_THINK_LLM":      "quick_think_llm",
    "TRADINGAGENTS_LLM_BACKEND_URL":      "backend_url",
    "TRADINGAGENTS_OUTPUT_LANGUAGE":      "output_language",
    "TRADINGAGENTS_MAX_DEBATE_ROUNDS":    "max_debate_rounds",
    "TRADINGAGENTS_MAX_RISK_ROUNDS":      "max_risk_discuss_rounds",
    "TRADINGAGENTS_CHECKPOINT_ENABLED":   "checkpoint_enabled",
    "TRADINGAGENTS_BENCHMARK_TICKER":     "benchmark_ticker",
    # Broker execution. Only scalars are exposed here; the per-rating target
    # weight table is a dict and is set in code or in a config override.
    "TRADINGAGENTS_EXECUTION_ENABLED":    "execution_enabled",
    "TRADINGAGENTS_EXECUTION_DRY_RUN":    "execution_dry_run",
    "TRADINGAGENTS_ALPACA_LIVE":          "alpaca_live",
    "TRADINGAGENTS_EXECUTION_JOURNAL":    "execution_journal_path",
    "TRADINGAGENTS_MAX_POSITION_WEIGHT":  "execution_max_position_weight",
    "TRADINGAGENTS_MAX_GROSS_EXPOSURE":   "execution_max_gross_exposure",
    "TRADINGAGENTS_MIN_ORDER_NOTIONAL":   "execution_min_order_notional",
    "TRADINGAGENTS_MAX_ORDERS_PER_DAY":   "execution_max_orders_per_day",
    # Kill switch
    "TRADINGAGENTS_KILL_SWITCH_ENABLED":  "risk_kill_switch_enabled",
    "TRADINGAGENTS_MAX_TOTAL_DRAWDOWN":   "risk_max_total_drawdown",
    "TRADINGAGENTS_MAX_DAILY_DRAWDOWN":   "risk_max_daily_drawdown",
    "TRADINGAGENTS_FLATTEN_ON_HALT":      "risk_flatten_on_halt",
    "TRADINGAGENTS_RISK_STATE_PATH":      "risk_state_path",
    # Scheduled runner
    "TRADINGAGENTS_SCHEDULE_ENABLED":     "schedule_enabled",
    "TRADINGAGENTS_SCHEDULE_CRON":        "schedule_cron",
    "TRADINGAGENTS_SCHEDULE_TIMEZONE":    "schedule_timezone",
    "TRADINGAGENTS_WATCHLIST_PATH":       "watchlist_path",
    "TRADINGAGENTS_RUN_HISTORY_PATH":     "run_history_path",
    "TRADINGAGENTS_RUN_MAX_TICKERS":      "run_max_tickers",
}


def _coerce(value: str, reference):
    """Coerce env-var string to the type of the existing default value."""
    if isinstance(reference, bool):
        return value.strip().lower() in ("true", "1", "yes", "on")
    if isinstance(reference, int) and not isinstance(reference, bool):
        return int(value)
    if isinstance(reference, float):
        return float(value)
    return value


def _apply_env_overrides(config: dict) -> dict:
    """Apply TRADINGAGENTS_* env vars to the config dict in-place."""
    for env_var, key in _ENV_OVERRIDES.items():
        raw = os.environ.get(env_var)
        if raw is None or raw == "":
            continue
        config[key] = _coerce(raw, config.get(key))
    return config


DEFAULT_CONFIG = _apply_env_overrides({
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", os.path.join(_TRADINGAGENTS_HOME, "logs")),
    "data_cache_dir": os.getenv("TRADINGAGENTS_CACHE_DIR", os.path.join(_TRADINGAGENTS_HOME, "cache")),
    "memory_log_path": os.getenv("TRADINGAGENTS_MEMORY_LOG_PATH", os.path.join(_TRADINGAGENTS_HOME, "memory", "trading_memory.md")),
    # Optional cap on the number of resolved memory log entries. When set,
    # the oldest resolved entries are pruned once this limit is exceeded.
    # Pending entries are never pruned. None disables rotation entirely.
    "memory_log_max_entries": None,
    # LLM settings
    "llm_provider": "openai",
    "deep_think_llm": "gpt-5.4",
    "quick_think_llm": "gpt-5.4-mini",
    # When None, each provider's client falls back to its own default endpoint
    # (api.openai.com for OpenAI, generativelanguage.googleapis.com for Gemini, ...).
    # The CLI overrides this per provider when the user picks one. Keeping a
    # provider-specific URL here would leak (e.g. OpenAI's /v1 was previously
    # being forwarded to Gemini, producing malformed request URLs).
    "backend_url": None,
    # Provider-specific thinking configuration
    "google_thinking_level": None,      # "high", "minimal", etc.
    "openai_reasoning_effort": None,    # "medium", "high", "low"
    "anthropic_effort": None,           # "high", "medium", "low"
    # Checkpoint/resume: when True, LangGraph saves state after each node
    # so a crashed run can resume from the last successful step.
    "checkpoint_enabled": False,
    # Output language for analyst reports and final decision
    # Internal agent debate stays in English for reasoning quality
    "output_language": "English",
    # Debate and discussion settings
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,
    "analyst_concurrency_limit": 1,
    # News / data fetching parameters
    # Increase for longer lookback strategies or to broaden macro coverage;
    # decrease to reduce token usage in agent prompts.
    "news_article_limit": 20,             # max articles per ticker (ticker-news)
    "global_news_article_limit": 10,      # max articles for global/macro news
    "global_news_lookback_days": 7,       # macro news lookback window
    # Search queries used by get_global_news for macro headlines. Extend or
    # replace to broaden geographic / sector coverage.
    "global_news_queries": [
        "Federal Reserve interest rates inflation",
        "S&P 500 earnings GDP economic outlook",
        "geopolitical risk trade war sanctions",
        "ECB Bank of England BOJ central bank policy",
        "oil commodities supply chain energy",
    ],
    # Data vendor configuration
    # Category-level configuration (default for all tools in category)
    "data_vendors": {
        "core_stock_apis": "yfinance",       # Options: alpha_vantage, yfinance
        "technical_indicators": "yfinance",  # Options: alpha_vantage, yfinance
        "fundamental_data": "yfinance",      # Options: alpha_vantage, yfinance
        "news_data": "yfinance",             # Options: alpha_vantage, yfinance
    },
    # Tool-level configuration (takes precedence over category-level)
    "tool_vendors": {
        # Example: "get_stock_data": "alpha_vantage",  # Override category default
    },
    # Benchmark for alpha calculation in the reflection layer.
    # ``benchmark_ticker`` (when set) overrides the suffix map for all
    # tickers; leave it None to use ``benchmark_map`` for auto-detection
    # based on the ticker's exchange suffix. SPY remains the US default
    # so the reflection label keeps reading "Alpha vs SPY" for US tickers
    # while non-US tickers get their regional index automatically.
    "benchmark_ticker": None,
    # Broker execution (tradingagents.execution).
    # Money can only move when execution_enabled is True AND execution_dry_run
    # is False. Reaching a real-money account additionally needs alpaca_live
    # True and TRADINGAGENTS_ALPACA_ALLOW_LIVE set in the environment; any one
    # of those four left at its default keeps orders off the live endpoint.
    "execution_enabled": False,
    "execution_dry_run": True,
    "alpaca_live": False,
    # None puts the journal under data_cache_dir/execution/journal.jsonl.
    "execution_journal_path": None,
    # Target fraction of account equity per 5-tier rating. None means "leave
    # the position alone" — a Hold does not resize anything.
    "execution_target_weights": {
        "Buy": 0.08,
        "Overweight": 0.04,
        "Hold": None,
        "Underweight": 0.02,
        "Sell": 0.0,
    },
    "execution_max_position_weight": 0.10,   # per-name cap, fraction of equity
    "execution_max_gross_exposure": 0.80,    # total invested cap, fraction of equity
    "execution_min_order_notional": 10.0,    # skip dust rebalances
    "execution_max_orders_per_day": 20,      # bounds damage from a runaway loop
    # Alpaca supports fractional shares, so buys are placed as notional
    # orders. Set False for whole-share-only accounts or instruments.
    "execution_fractional_shares": True,
    # Market-hours check. Leave False: notional and fractional orders are
    # rejected outside regular trading hours anyway.
    "execution_allow_when_market_closed": False,
    # Kill switch. Drawdown is measured against the all-time equity high-water
    # mark (total) and against the equity at the start of the UTC day (daily).
    # A tripped switch blocks every order and is only cleared by a human.
    "risk_kill_switch_enabled": True,
    "risk_max_total_drawdown": 0.15,   # halt at 15% below the high-water mark
    "risk_max_daily_drawdown": 0.05,   # halt at 5% below today's open
    # Selling everything is itself a large, irreversible action, so a halt
    # does not liquidate unless this is explicitly turned on.
    "risk_flatten_on_halt": False,
    "risk_state_path": None,           # defaults under data_cache_dir/execution
    # Scheduled runner. Off by default: enabling it is what turns the
    # framework into something that trades without a human present.
    "schedule_enabled": False,
    "schedule_cron": "30 13 * * 1-5",  # 13:30 UTC weekdays (pre-US-open)
    "schedule_timezone": "UTC",
    "watchlist_path": None,            # defaults under data_cache_dir
    "run_history_path": None,          # defaults under data_cache_dir
    # Bounds the cost and duration of one scheduled pass. A full analysis is
    # many LLM calls per ticker, so this is a spend limit as much as a time one.
    "run_max_tickers": 10,
    "benchmark_map": {
        ".NS":  "^NSEI",    # NSE India (Nifty 50)
        ".BO":  "^BSESN",   # BSE India (Sensex)
        ".T":   "^N225",    # Tokyo (Nikkei 225)
        ".HK":  "^HSI",     # Hong Kong (Hang Seng)
        ".L":   "^FTSE",    # London (FTSE 100)
        ".TO":  "^GSPTSE",  # Toronto (TSX Composite)
        ".AX":  "^AXJO",    # Australia (ASX 200)
        "":     "SPY",      # default for US-listed tickers (no suffix)
    },
})
