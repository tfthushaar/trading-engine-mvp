"""
Strategy Interpreter — converts JSON entry/exit conditions from
trading_strategies into callable signal functions for backtesting.

Each condition type is mapped to a function that receives the current
row of market data (plus lookback context) and returns True/False.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from utils.logger import get_logger

logger = get_logger(__name__)

# Type alias: a signal function takes (current_row, history) → bool
SignalFunc = Callable[[dict[str, Any], list[dict[str, Any]]], bool]


class StrategyInterpreter:
    """Parses JSON strategy conditions into executable signal functions."""

    def interpret(
        self, strategy: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Convert a strategy dict into executable components.

        Returns
        -------
        dict | None
            Keys: entry_signals, exit_signals, risk_rules, position_sizing,
                  asset, direction, holding_period_days.
            Returns ``None`` if the strategy cannot be interpreted.
        """
        try:
            entry_conds = self._parse_json_field(
                strategy.get("entry_conditions", "[]")
            )
            exit_conds = self._parse_json_field(
                strategy.get("exit_conditions", "[]")
            )
            risk_rules = self._parse_json_field(
                strategy.get("risk_rules", "{}")
            )
            position_sizing = self._parse_json_field(
                strategy.get("position_sizing", "{}")
            )
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning(
                "Cannot parse strategy '%s': %s",
                strategy.get("strategy_name", ""), exc,
            )
            return None

        entry_signals = self._build_entry_signals(entry_conds)
        exit_signals = self._build_exit_signals(exit_conds, risk_rules)

        if not entry_signals:
            logger.warning(
                "No interpretable entry conditions for '%s'.",
                strategy.get("strategy_name", ""),
            )
            return None

        # Resolve asset tickers from asset_scope
        asset = self._resolve_asset(strategy.get("asset_scope", ""))
        direction = self._resolve_direction(entry_conds, strategy)
        holding_days = self._parse_holding_period(
            strategy.get("holding_period", "")
        )

        # Parse stop-loss and take-profit from risk_rules
        stop_loss_pct = self._extract_stop_loss(risk_rules)
        take_profit_pct = self._extract_take_profit(risk_rules)

        return {
            "entry_signals": entry_signals,
            "exit_signals": exit_signals,
            "risk_rules": risk_rules,
            "position_sizing": position_sizing,
            "asset": asset,
            "direction": direction,
            "holding_period_days": holding_days,
            "stop_loss_pct": stop_loss_pct,
            "take_profit_pct": take_profit_pct,
        }

    # ------------------------------------------------------------------
    # JSON parsing
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_json_field(value: Any) -> Any:
        """Parse a JSON string or pass through dicts/lists."""
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            value = value.strip()
            if not value or value in ("null", "None"):
                return {}
            return json.loads(value)
        return {}

    # ------------------------------------------------------------------
    # Entry signal builders
    # ------------------------------------------------------------------
    def _build_entry_signals(
        self, conditions: list | dict
    ) -> list[SignalFunc]:
        """Build a list of callable entry signal functions."""
        if isinstance(conditions, dict):
            conditions = [conditions]
        if not isinstance(conditions, list):
            return []

        signals: list[SignalFunc] = []
        for cond in conditions:
            if not isinstance(cond, dict):
                continue
            ctype = cond.get("type", "").lower()
            func = self._build_condition(cond, ctype)
            if func:
                signals.append(func)

        return signals

    def _build_exit_signals(
        self, conditions: list | dict, risk_rules: dict | list
    ) -> list[SignalFunc]:
        """Build exit signal functions (including risk-based exits)."""
        if isinstance(conditions, dict):
            conditions = [conditions]
        if not isinstance(conditions, list):
            conditions = []

        signals: list[SignalFunc] = []
        for cond in conditions:
            if not isinstance(cond, dict):
                continue
            ctype = cond.get("type", "").lower()
            func = self._build_condition(cond, ctype)
            if func:
                signals.append(func)

        return signals

    def _build_condition(
        self, cond: dict[str, Any], ctype: str
    ) -> SignalFunc | None:
        """Map a condition type to a callable signal function."""
        builders = {
            "price_momentum": self._momentum_signal,
            "momentum": self._momentum_signal,
            "price_deviation": self._mean_reversion_signal,
            "mean_reversion": self._mean_reversion_signal,
            "sentiment_threshold": self._sentiment_signal,
            "sentiment_confirmation": self._sentiment_signal,
            "sentiment_price_divergence": self._sentiment_signal,
            "event_trigger": self._event_signal,
            "macro_shift": self._macro_signal,
            "macro_confirmation": self._macro_signal,
            "time_exit": self._time_exit_signal,
            "stop_loss": self._stop_loss_signal,
            "take_profit": self._take_profit_signal,
            "trailing_stop": self._trailing_stop_signal,
            "price_target": self._price_target_signal,
            "technical_exit": self._technical_exit_signal,
        }
        builder = builders.get(ctype)
        if builder:
            return builder(cond)

        # Fallback: try to interpret from the "rule" text
        rule_text = str(cond.get("rule", "")).lower()
        if "momentum" in rule_text or "moving average" in rule_text:
            return self._momentum_signal(cond)
        if "oversold" in rule_text or "overbought" in rule_text:
            return self._mean_reversion_signal(cond)
        if "stop" in rule_text and "loss" in rule_text:
            return self._stop_loss_signal(cond)

        logger.debug("Unrecognised condition type: %s", ctype)
        return None

    # ------------------------------------------------------------------
    # Individual signal functions
    # ------------------------------------------------------------------
    def _momentum_signal(self, cond: dict) -> SignalFunc:
        """Price momentum: close > SMA(lookback)."""
        lookback = int(cond.get("lookback_days", cond.get("period", 20)))
        threshold = float(cond.get("threshold", cond.get("min_return", 0.0)))

        def signal(row: dict, history: list[dict]) -> bool:
            if len(history) < lookback:
                return False
            recent = history[-lookback:]
            closes = [r["close"] for r in recent if r.get("close")]
            if not closes:
                return False
            sma = sum(closes) / len(closes)
            current = row.get("close", 0)
            if sma == 0:
                return False
            return (current - sma) / sma > threshold / 100.0

        return signal

    def _mean_reversion_signal(self, cond: dict) -> SignalFunc:
        """Mean reversion: close deviates > N std devs from SMA."""
        lookback = int(cond.get("lookback_days", cond.get("period", 20)))
        std_devs = float(cond.get("std_deviations", cond.get("threshold", 2.0)))

        def signal(row: dict, history: list[dict]) -> bool:
            if len(history) < lookback:
                return False
            recent = history[-lookback:]
            closes = [r["close"] for r in recent if r.get("close")]
            if len(closes) < 2:
                return False
            mean = sum(closes) / len(closes)
            variance = sum((c - mean) ** 2 for c in closes) / len(closes)
            std = variance ** 0.5
            if std == 0:
                return False
            current = row.get("close", 0)
            z_score = (current - mean) / std
            # Entry on oversold (z < -threshold) or overbought (z > threshold)
            return abs(z_score) > std_devs

        return signal

    def _sentiment_signal(self, cond: dict) -> SignalFunc:
        """Sentiment threshold — always returns True (sentiment data
        is incorporated at strategy level; backtest uses price-only
        simulation for simplicity)."""
        def signal(row: dict, history: list[dict]) -> bool:
            return True
        return signal

    def _event_signal(self, cond: dict) -> SignalFunc:
        """Event trigger — always True (events pre-filtered upstream)."""
        def signal(row: dict, history: list[dict]) -> bool:
            return True
        return signal

    def _macro_signal(self, cond: dict) -> SignalFunc:
        """Macro shift — always True (macro filtering done upstream)."""
        def signal(row: dict, history: list[dict]) -> bool:
            return True
        return signal

    def _time_exit_signal(self, cond: dict) -> SignalFunc:
        """Time-based exit — handled by holding_period in executor."""
        def signal(row: dict, history: list[dict]) -> bool:
            return False
        return signal

    def _stop_loss_signal(self, cond: dict) -> SignalFunc:
        """Stop-loss exit — handled by portfolio_simulator."""
        def signal(row: dict, history: list[dict]) -> bool:
            return False
        return signal

    def _take_profit_signal(self, cond: dict) -> SignalFunc:
        """Take-profit exit — handled by portfolio_simulator."""
        def signal(row: dict, history: list[dict]) -> bool:
            return False
        return signal

    def _trailing_stop_signal(self, cond: dict) -> SignalFunc:
        """Trailing stop — handled by portfolio_simulator."""
        def signal(row: dict, history: list[dict]) -> bool:
            return False
        return signal

    def _price_target_signal(self, cond: dict) -> SignalFunc:
        """Price target exit — simple threshold check."""
        def signal(row: dict, history: list[dict]) -> bool:
            return False  # Handled by portfolio simulator via take_profit
        return signal

    def _technical_exit_signal(self, cond: dict) -> SignalFunc:
        """Technical exit — reverse of momentum entry."""
        lookback = int(cond.get("lookback_days", cond.get("period", 20)))

        def signal(row: dict, history: list[dict]) -> bool:
            if len(history) < lookback:
                return False
            recent = history[-lookback:]
            closes = [r["close"] for r in recent if r.get("close")]
            if not closes:
                return False
            sma = sum(closes) / len(closes)
            current = row.get("close", 0)
            return current < sma  # Exit when price falls below SMA

        return signal

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_asset(asset_scope: str) -> str:
        """Extract the primary ticker from asset_scope."""
        if not asset_scope:
            return "SPY"
        # Try to find a ticker symbol
        scope = asset_scope.strip().upper()
        # If it looks like a single ticker
        match = re.match(r"^[\^]?[A-Z]{1,5}$", scope)
        if match:
            return scope
        # Extract first ticker-like word
        tokens = re.findall(r"\b[\^]?[A-Z]{1,5}\b", scope)
        if tokens:
            return tokens[0]
        # Sector mappings to ETFs
        sector_etf = {
            "TECHNOLOGY": "XLK", "TECH": "XLK",
            "BANKING": "XLF", "FINANCE": "XLF", "FINANCIAL": "XLF",
            "ENERGY": "XLE",
            "HEALTHCARE": "XLV", "HEALTH": "XLV",
            "CONSUMER": "XLY",
            "INDUSTRIAL": "XLI",
        }
        for key, etf in sector_etf.items():
            if key in scope:
                return etf
        return "SPY"

    @staticmethod
    def _resolve_direction(
        entry_conds: list | dict, strategy: dict
    ) -> str:
        """Determine trade direction: 'long' or 'short'."""
        text = json.dumps(entry_conds).lower()
        text += " " + str(strategy.get("strategy_name", "")).lower()
        if any(w in text for w in ("short", "bearish", "sell", "put")):
            return "short"
        return "long"

    @staticmethod
    def _parse_holding_period(hp: str) -> int:
        """Parse holding_period string into number of trading days."""
        if not hp:
            return 20  # default ~1 month
        hp_lower = hp.lower().strip()
        # Extract number
        nums = re.findall(r"(\d+)", hp_lower)
        if not nums:
            # Named periods
            mapping = {
                "intraday": 1, "1d": 1, "daily": 1,
                "1w": 5, "week": 5,
                "2w": 10, "two week": 10,
                "1m": 20, "month": 20,
                "3m": 63, "quarter": 63,
                "6m": 126,
                "1y": 252, "year": 252,
            }
            for key, days in mapping.items():
                if key in hp_lower:
                    return days
            return 20

        n = int(nums[0])
        if "day" in hp_lower or "d" in hp_lower:
            return max(n, 1)
        elif "week" in hp_lower or "w" in hp_lower:
            return n * 5
        elif "month" in hp_lower or "m" in hp_lower:
            return n * 20
        elif "year" in hp_lower or "y" in hp_lower:
            return n * 252
        return n

    @staticmethod
    def _extract_stop_loss(risk_rules: dict | list) -> float:
        """Extract stop-loss percentage from risk rules."""
        if isinstance(risk_rules, list):
            risk_rules = risk_rules[0] if risk_rules else {}
        if not isinstance(risk_rules, dict):
            return 5.0  # default 5%
        # Look for stop_loss_pct or similar keys
        for key in ("stop_loss_pct", "stop_loss", "max_loss_pct"):
            val = risk_rules.get(key)
            if val is not None:
                return abs(float(val))
        # Try to extract from text
        text = json.dumps(risk_rules).lower()
        match = re.search(r"stop.?loss.*?(\d+(?:\.\d+)?)\s*%?", text)
        if match:
            return float(match.group(1))
        return 5.0  # default

    @staticmethod
    def _extract_take_profit(risk_rules: dict | list) -> float | None:
        """Extract take-profit percentage from risk rules."""
        if isinstance(risk_rules, list):
            risk_rules = risk_rules[0] if risk_rules else {}
        if not isinstance(risk_rules, dict):
            return None
        for key in ("take_profit_pct", "take_profit", "profit_target_pct"):
            val = risk_rules.get(key)
            if val is not None:
                return abs(float(val))
        return None
