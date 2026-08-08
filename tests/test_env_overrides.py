"""Tests for TRADINGAGENTS_* env-var overlay onto DEFAULT_CONFIG."""

from __future__ import annotations

import importlib

import pytest

import tradingagents.default_config as default_config_module


def _reload_with_env(monkeypatch, **overrides):
    """Set/clear env vars then reload default_config to re-evaluate DEFAULT_CONFIG."""
    for key in list(default_config_module._ENV_OVERRIDES):
        monkeypatch.delenv(key, raising=False)
    for key, val in overrides.items():
        monkeypatch.setenv(key, val)
    return importlib.reload(default_config_module)


def test_no_env_uses_built_in_defaults(monkeypatch):
    dc = _reload_with_env(monkeypatch)
    assert dc.DEFAULT_CONFIG["llm_provider"] == "openai"
    assert dc.DEFAULT_CONFIG["deep_think_llm"] == "gpt-5.4"
    assert dc.DEFAULT_CONFIG["quick_think_llm"] == "gpt-5.4-mini"
    assert dc.DEFAULT_CONFIG["backend_url"] is None
    assert dc.DEFAULT_CONFIG["max_debate_rounds"] == 1
    assert dc.DEFAULT_CONFIG["checkpoint_enabled"] is False


def test_string_overrides(monkeypatch):
    dc = _reload_with_env(
        monkeypatch,
        TRADINGAGENTS_LLM_PROVIDER="google",
        TRADINGAGENTS_DEEP_THINK_LLM="gemini-3-pro-preview",
        TRADINGAGENTS_QUICK_THINK_LLM="gemini-3-flash-preview",
        TRADINGAGENTS_LLM_BACKEND_URL="https://example.invalid/v1",
        TRADINGAGENTS_OUTPUT_LANGUAGE="Chinese",
    )
    assert dc.DEFAULT_CONFIG["llm_provider"] == "google"
    assert dc.DEFAULT_CONFIG["deep_think_llm"] == "gemini-3-pro-preview"
    assert dc.DEFAULT_CONFIG["quick_think_llm"] == "gemini-3-flash-preview"
    assert dc.DEFAULT_CONFIG["backend_url"] == "https://example.invalid/v1"
    assert dc.DEFAULT_CONFIG["output_language"] == "Chinese"


def test_int_coercion(monkeypatch):
    dc = _reload_with_env(
        monkeypatch,
        TRADINGAGENTS_MAX_DEBATE_ROUNDS="3",
        TRADINGAGENTS_MAX_RISK_ROUNDS="2",
    )
    assert dc.DEFAULT_CONFIG["max_debate_rounds"] == 3
    assert isinstance(dc.DEFAULT_CONFIG["max_debate_rounds"], int)
    assert dc.DEFAULT_CONFIG["max_risk_discuss_rounds"] == 2
    assert isinstance(dc.DEFAULT_CONFIG["max_risk_discuss_rounds"], int)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("true", True), ("True", True), ("1", True), ("yes", True), ("on", True),
        ("false", False), ("False", False), ("0", False), ("no", False), ("off", False),
    ],
)
def test_bool_coercion(monkeypatch, raw, expected):
    dc = _reload_with_env(monkeypatch, TRADINGAGENTS_CHECKPOINT_ENABLED=raw)
    assert dc.DEFAULT_CONFIG["checkpoint_enabled"] is expected


def test_empty_env_value_is_passthrough(monkeypatch):
    """Empty TRADINGAGENTS_* values must not clobber the built-in default."""
    dc = _reload_with_env(
        monkeypatch,
        TRADINGAGENTS_LLM_PROVIDER="",
        TRADINGAGENTS_MAX_DEBATE_ROUNDS="",
    )
    assert dc.DEFAULT_CONFIG["llm_provider"] == "openai"
    assert dc.DEFAULT_CONFIG["max_debate_rounds"] == 1


def test_invalid_int_raises(monkeypatch):
    """Garbage int values should surface a ValueError at import, not silently misconfigure."""
    monkeypatch.setenv("TRADINGAGENTS_MAX_DEBATE_ROUNDS", "not-a-number")
    with pytest.raises(ValueError):
        importlib.reload(default_config_module)
    # Restore module state for subsequent tests in this process
    monkeypatch.delenv("TRADINGAGENTS_MAX_DEBATE_ROUNDS", raising=False)
    importlib.reload(default_config_module)


def test_unknown_env_var_is_ignored(monkeypatch):
    """Env vars outside _ENV_OVERRIDES must not bleed into DEFAULT_CONFIG."""
    dc = _reload_with_env(
        monkeypatch,
        TRADINGAGENTS_NONEXISTENT_KEY="oops",
    )
    assert "nonexistent_key" not in dc.DEFAULT_CONFIG


def test_execution_defaults_are_the_safe_ones(monkeypatch):
    """Every execution switch must default to the setting that moves no money."""
    dc = _reload_with_env(monkeypatch)
    assert dc.DEFAULT_CONFIG["execution_enabled"] is False
    assert dc.DEFAULT_CONFIG["execution_dry_run"] is True
    assert dc.DEFAULT_CONFIG["alpaca_live"] is False
    assert dc.DEFAULT_CONFIG["execution_journal_path"] is None


def test_execution_overrides_coerce_by_default_type(monkeypatch):
    dc = _reload_with_env(
        monkeypatch,
        TRADINGAGENTS_EXECUTION_ENABLED="true",
        TRADINGAGENTS_EXECUTION_DRY_RUN="false",
        TRADINGAGENTS_ALPACA_LIVE="1",
        TRADINGAGENTS_EXECUTION_JOURNAL="/tmp/journal.jsonl",
        TRADINGAGENTS_MAX_POSITION_WEIGHT="0.05",
        TRADINGAGENTS_MAX_GROSS_EXPOSURE="0.5",
        TRADINGAGENTS_MIN_ORDER_NOTIONAL="25",
        TRADINGAGENTS_MAX_ORDERS_PER_DAY="5",
    )
    assert dc.DEFAULT_CONFIG["execution_enabled"] is True
    assert dc.DEFAULT_CONFIG["execution_dry_run"] is False
    assert dc.DEFAULT_CONFIG["alpaca_live"] is True
    assert dc.DEFAULT_CONFIG["execution_journal_path"] == "/tmp/journal.jsonl"
    assert dc.DEFAULT_CONFIG["execution_max_position_weight"] == 0.05
    assert dc.DEFAULT_CONFIG["execution_max_gross_exposure"] == 0.5
    assert dc.DEFAULT_CONFIG["execution_min_order_notional"] == 25.0
    assert dc.DEFAULT_CONFIG["execution_max_orders_per_day"] == 5


def test_risk_and_schedule_defaults(monkeypatch):
    """The kill switch defaults on; the scheduler defaults off."""
    dc = _reload_with_env(monkeypatch)
    assert dc.DEFAULT_CONFIG["risk_kill_switch_enabled"] is True
    assert dc.DEFAULT_CONFIG["risk_max_total_drawdown"] == 0.15
    assert dc.DEFAULT_CONFIG["risk_max_daily_drawdown"] == 0.05
    assert dc.DEFAULT_CONFIG["risk_flatten_on_halt"] is False
    assert dc.DEFAULT_CONFIG["schedule_enabled"] is False
    assert dc.DEFAULT_CONFIG["run_max_tickers"] == 10


def test_risk_and_schedule_overrides(monkeypatch):
    dc = _reload_with_env(
        monkeypatch,
        TRADINGAGENTS_KILL_SWITCH_ENABLED="false",
        TRADINGAGENTS_MAX_TOTAL_DRAWDOWN="0.2",
        TRADINGAGENTS_MAX_DAILY_DRAWDOWN="0.08",
        TRADINGAGENTS_FLATTEN_ON_HALT="true",
        TRADINGAGENTS_SCHEDULE_ENABLED="true",
        TRADINGAGENTS_SCHEDULE_CRON="0 14 * * 1-5",
        TRADINGAGENTS_SCHEDULE_TIMEZONE="America/New_York",
        TRADINGAGENTS_RUN_MAX_TICKERS="3",
    )
    assert dc.DEFAULT_CONFIG["risk_kill_switch_enabled"] is False
    assert dc.DEFAULT_CONFIG["risk_max_total_drawdown"] == 0.2
    assert dc.DEFAULT_CONFIG["risk_max_daily_drawdown"] == 0.08
    assert dc.DEFAULT_CONFIG["risk_flatten_on_halt"] is True
    assert dc.DEFAULT_CONFIG["schedule_enabled"] is True
    assert dc.DEFAULT_CONFIG["schedule_cron"] == "0 14 * * 1-5"
    assert dc.DEFAULT_CONFIG["schedule_timezone"] == "America/New_York"
    assert dc.DEFAULT_CONFIG["run_max_tickers"] == 3
