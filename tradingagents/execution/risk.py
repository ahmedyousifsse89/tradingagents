"""Drawdown kill switch: the layer that stops trading when losses accumulate.

Every other guard in this package bounds a single order. This one bounds the
whole account over time. It tracks a high-water mark of equity, halts trading
when the account falls a configured distance below it, and refuses to lift
that halt on its own — a tripped kill switch is cleared by a human, because
the condition that tripped it is exactly the condition under which automated
judgement should not be trusted to decide it has passed.

State lives in a small JSON file so a container restart cannot silently reset
the high-water mark and re-enable a halted account.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# Why the switch tripped, or why it is currently blocking.
HALT_MANUAL = "manual"
HALT_TOTAL_DRAWDOWN = "total_drawdown"
HALT_DAILY_DRAWDOWN = "daily_drawdown"


@dataclass
class RiskState:
    """Persisted kill-switch state."""

    high_water_mark: float = 0.0
    day: str = ""                      # UTC date the day_open_equity belongs to
    day_open_equity: float = 0.0
    halted: bool = False
    halt_reason: str = ""
    halt_detail: str = ""
    halted_at: str = ""
    last_equity: float = 0.0
    updated_at: str = ""
    history: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict) -> "RiskState":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in raw.items() if k in known})


class KillSwitch:
    """Halt trading on drawdown, and stay halted until a human resumes.

    ``max_total_drawdown`` is measured against the all-time equity high-water
    mark; ``max_daily_drawdown`` against the equity at the start of the
    current UTC day. Either breach halts. Set a limit to ``None`` to disable
    that check.
    """

    def __init__(
        self,
        path: str | os.PathLike,
        *,
        max_total_drawdown: Optional[float] = 0.15,
        max_daily_drawdown: Optional[float] = 0.05,
        flatten_on_halt: bool = False,
    ):
        self.path = Path(path)
        self.max_total_drawdown = max_total_drawdown
        self.max_daily_drawdown = max_daily_drawdown
        self.flatten_on_halt = flatten_on_halt

    # ---- persistence -------------------------------------------------

    def load(self) -> RiskState:
        if not self.path.exists():
            return RiskState()
        try:
            return RiskState.from_dict(json.loads(self.path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, TypeError, ValueError):
            # A corrupt state file must not be read as "not halted". Fail
            # closed: report a halt that a human has to look at.
            logger.error("risk state at %s is unreadable; failing closed", self.path)
            return RiskState(
                halted=True,
                halt_reason=HALT_MANUAL,
                halt_detail=f"risk state file {self.path} is corrupt and was not trusted",
                halted_at=_now(),
            )

    def save(self, state: RiskState) -> None:
        state.updated_at = _now()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Temp file + replace so a crash mid-write cannot truncate the state
        # that decides whether trading is allowed.
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(asdict(state), indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    # ---- evaluation --------------------------------------------------

    def evaluate(self, equity: float, *, today: Optional[str] = None) -> RiskState:
        """Fold ``equity`` into the state and halt if a limit is breached.

        Called before every run. Returns the updated, already-persisted state.
        """
        state = self.load()
        today = today or datetime.now(timezone.utc).date().isoformat()

        if equity <= 0:
            # No usable equity reading: leave the marks alone rather than
            # resetting the high-water mark to zero.
            return state

        if state.high_water_mark <= 0:
            state.high_water_mark = equity
        if state.day != today:
            state.day = today
            state.day_open_equity = equity

        state.high_water_mark = max(state.high_water_mark, equity)
        state.last_equity = equity

        if not state.halted:
            breach = self._breach(state, equity)
            if breach is not None:
                reason, detail = breach
                state.halted = True
                state.halt_reason = reason
                state.halt_detail = detail
                state.halted_at = _now()
                state.history.append(
                    {"at": state.halted_at, "event": "halt", "reason": reason, "detail": detail}
                )
                logger.error("KILL SWITCH TRIPPED (%s): %s", reason, detail)

        self.save(state)
        return state

    def _breach(self, state: RiskState, equity: float):
        if self.max_total_drawdown is not None and state.high_water_mark > 0:
            drawdown = 1.0 - (equity / state.high_water_mark)
            if drawdown >= self.max_total_drawdown:
                return (
                    HALT_TOTAL_DRAWDOWN,
                    f"equity ${equity:,.2f} is {drawdown:.2%} below the high-water "
                    f"mark of ${state.high_water_mark:,.2f}; limit is "
                    f"{self.max_total_drawdown:.2%}",
                )

        if self.max_daily_drawdown is not None and state.day_open_equity > 0:
            drawdown = 1.0 - (equity / state.day_open_equity)
            if drawdown >= self.max_daily_drawdown:
                return (
                    HALT_DAILY_DRAWDOWN,
                    f"equity ${equity:,.2f} is {drawdown:.2%} below today's open of "
                    f"${state.day_open_equity:,.2f}; limit is "
                    f"{self.max_daily_drawdown:.2%}",
                )

        return None

    # ---- manual control ----------------------------------------------

    def halt(self, detail: str = "halted manually") -> RiskState:
        state = self.load()
        state.halted = True
        state.halt_reason = HALT_MANUAL
        state.halt_detail = detail
        state.halted_at = _now()
        state.history.append({"at": state.halted_at, "event": "halt", "reason": HALT_MANUAL, "detail": detail})
        self.save(state)
        return state

    def resume(self, detail: str = "resumed manually") -> RiskState:
        """Clear a halt. Deliberately only ever called by a human action.

        The high-water mark is also reset to current equity, so resuming does
        not leave the account one tick away from re-tripping on the same
        drawdown it was just cleared for.
        """
        state = self.load()
        state.halted = False
        state.halt_reason = ""
        state.halt_detail = ""
        state.halted_at = ""
        if state.last_equity > 0:
            state.high_water_mark = state.last_equity
            state.day_open_equity = state.last_equity
        state.history.append({"at": _now(), "event": "resume", "reason": HALT_MANUAL, "detail": detail})
        self.save(state)
        return state

    def status(self) -> dict:
        """Serialisable snapshot for the API and the dashboard."""
        state = self.load()
        equity = state.last_equity
        total_dd = (
            1.0 - (equity / state.high_water_mark)
            if state.high_water_mark > 0 and equity > 0
            else 0.0
        )
        daily_dd = (
            1.0 - (equity / state.day_open_equity)
            if state.day_open_equity > 0 and equity > 0
            else 0.0
        )
        return {
            "halted": state.halted,
            "halt_reason": state.halt_reason,
            "halt_detail": state.halt_detail,
            "halted_at": state.halted_at,
            "equity": equity,
            "high_water_mark": state.high_water_mark,
            "day_open_equity": state.day_open_equity,
            "total_drawdown": total_dd,
            "daily_drawdown": daily_dd,
            "max_total_drawdown": self.max_total_drawdown,
            "max_daily_drawdown": self.max_daily_drawdown,
            "updated_at": state.updated_at,
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_risk_state_path(config: dict) -> Optional[str]:
    """Kill-switch state file location, defaulting under the data cache dir."""
    configured = config.get("risk_state_path")
    if configured:
        return configured
    cache_dir = config.get("data_cache_dir")
    if not cache_dir:
        return None
    return os.path.join(cache_dir, "execution", "risk_state.json")


def kill_switch_from_config(config: dict) -> Optional[KillSwitch]:
    """Build a :class:`KillSwitch` from config, or None when it is disabled."""
    if not config.get("risk_kill_switch_enabled", True):
        return None
    path = default_risk_state_path(config)
    if path is None:
        return None
    return KillSwitch(
        path,
        max_total_drawdown=config.get("risk_max_total_drawdown", 0.15),
        max_daily_drawdown=config.get("risk_max_daily_drawdown", 0.05),
        flatten_on_halt=config.get("risk_flatten_on_halt", False),
    )
