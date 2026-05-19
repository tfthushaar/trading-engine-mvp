"""
Strategy Validator — rule-based quality gate that rejects strategies
with missing, incomplete, or logically inconsistent rules.

Rejection criteria
------------------
1. Missing or empty entry conditions
2. Missing or empty exit conditions
3. Undefined time horizon (no holding_period)
4. Conflicting rules (entry direction contradicts exit direction)
5. Cannot be backtested (no known asset reference)
6. Missing risk management (no stop_loss or position sizing)
"""

from __future__ import annotations

import json
import re
from typing import Any

from utils.config import KNOWN_TICKERS, SECTOR_MAPPING
from utils.logger import get_logger

logger = get_logger(__name__)

_SECTOR_NAMES = {s.lower() for s in SECTOR_MAPPING}


class StrategyValidator:
    """Validates strategies and returns only those passing all gates."""

    def validate(
        self, strategies: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Apply all validation rules.

        Strategies that pass are marked ``status = 'validated'``.
        Rejected strategies are logged and discarded.

        Parameters
        ----------
        strategies
            Raw parsed strategy dicts.

        Returns
        -------
        list[dict]
            Strategies that pass all validation rules.
        """
        accepted: list[dict[str, Any]] = []

        for s in strategies:
            reason = self._check(s)
            if reason:
                s["status"] = "rejected"
                logger.info(
                    "Rejected strategy '%s': %s",
                    (s.get("strategy_name") or "")[:60], reason,
                )
                continue
            s["status"] = "validated"
            accepted.append(s)

        logger.info(
            "Validation passed %d / %d strategies.",
            len(accepted), len(strategies),
        )
        return accepted

    # ------------------------------------------------------------------
    # Gate logic
    # ------------------------------------------------------------------
    def _check(self, s: dict[str, Any]) -> str | None:
        """Return a rejection reason, or ``None`` if the strategy passes."""

        # 1. Entry conditions
        entry = s.get("entry_conditions", "")
        if not self._has_conditions(entry):
            return "missing or empty entry_conditions"

        # 2. Exit conditions
        exit_conds = s.get("exit_conditions", "")
        if not self._has_conditions(exit_conds):
            return "missing or empty exit_conditions"

        # 3. Holding period
        if not s.get("holding_period"):
            return "undefined holding_period"

        # 4. Conflicting rules check
        conflict = self._check_conflicts(s)
        if conflict:
            return conflict

        # 5. Backtestability — must reference known assets
        name = s.get("strategy_name", "")
        scope = s.get("asset_scope", "")
        entry_str = entry if isinstance(entry, str) else json.dumps(entry)
        combined_text = f"{name} {scope} {entry_str}"
        if not self._has_asset_reference(combined_text):
            return "no known asset reference — cannot be backtested"

        # 6. Risk management
        risk = s.get("risk_rules", "")
        if not self._has_risk_management(risk):
            return "missing risk management (no stop_loss or sizing)"

        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _has_conditions(value: Any) -> bool:
        """Check whether a conditions field is non-empty."""
        if not value:
            return False
        if isinstance(value, str):
            value = value.strip()
            if not value or value in ("[]", "{}", '""', "null"):
                return False
            # Try parsing as JSON
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list) and len(parsed) == 0:
                    return False
                if isinstance(parsed, dict) and len(parsed) == 0:
                    return False
            except json.JSONDecodeError:
                # Plain text condition — acceptable
                pass
            return True
        if isinstance(value, (list, dict)):
            return len(value) > 0
        return False

    @staticmethod
    def _check_conflicts(s: dict[str, Any]) -> str | None:
        """Check for logical conflicts between entry and exit conditions."""
        entry_str = str(s.get("entry_conditions", "")).lower()
        exit_str = str(s.get("exit_conditions", "")).lower()

        # Detect contradictory direction signals
        bullish_entry = any(
            w in entry_str for w in ("bullish", "long", "buy", "upside")
        )
        bearish_exit = any(
            w in exit_str for w in ("bullish breakout", "buy signal")
        )
        if bullish_entry and bearish_exit:
            return "conflicting rules: bullish entry with bullish exit trigger"

        bearish_entry = any(
            w in entry_str for w in ("bearish", "short", "sell", "downside")
        )
        bullish_exit_trigger = any(
            w in exit_str for w in ("bearish breakdown", "sell signal")
        )
        if bearish_entry and bullish_exit_trigger:
            return "conflicting rules: bearish entry with bearish exit trigger"

        return None

    @staticmethod
    def _has_asset_reference(text: str) -> bool:
        """Check whether text references at least one known ticker,
        sector, or asset class."""
        upper = text.upper()
        for ticker in KNOWN_TICKERS:
            if re.search(r"\b" + re.escape(ticker) + r"\b", upper):
                return True
        lower = text.lower()
        for sector in _SECTOR_NAMES:
            if sector in lower:
                return True
        # Accept generic asset references
        for term in ("s&p", "treasury", "bond", "gold", "crude",
                     "index", "etf", "sector", "equity", "stock"):
            if term in lower:
                return True
        return False

    @staticmethod
    def _has_risk_management(risk: Any) -> bool:
        """Check whether risk rules include stop_loss or sizing info."""
        if not risk:
            return False
        risk_str = str(risk).lower()
        has_stop = "stop" in risk_str or "loss" in risk_str
        has_sizing = "position" in risk_str or "sizing" in risk_str
        # Also check for numeric stop loss
        has_numeric_stop = bool(
            re.search(r"stop.?loss.{0,10}\d", risk_str)
        )
        return has_stop or has_sizing or has_numeric_stop
