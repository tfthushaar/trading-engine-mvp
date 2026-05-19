"""
Trade Executor — iterates through historical price data and generates
trade signals by evaluating interpreted entry/exit conditions day by day.

Produces a list of Trade dicts with entry/exit timestamps, prices,
direction, and holding period.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)


class TradeExecutor:
    """Scans price history and emits trades based on signal functions."""

    def execute(
        self,
        price_data: list[dict[str, Any]],
        interpreted: dict[str, Any],
        strategy_id: str,
    ) -> list[dict[str, Any]]:
        """Generate trades from historical prices and interpreted signals.

        Parameters
        ----------
        price_data
            Chronologically sorted OHLCV dicts from ``stock_prices``.
        interpreted
            Output from ``StrategyInterpreter.interpret()``.
        strategy_id
            Strategy identifier for tagging trades.

        Returns
        -------
        list[dict]
            Trade dicts ready for portfolio simulation.
        """
        if not price_data or not interpreted:
            return []

        entry_signals = interpreted["entry_signals"]
        exit_signals = interpreted.get("exit_signals", [])
        direction = interpreted.get("direction", "long")
        holding_limit = interpreted.get("holding_period_days", 20)
        asset = interpreted.get("asset", "SPY")

        trades: list[dict[str, Any]] = []
        in_position = False
        entry_row: dict[str, Any] | None = None
        entry_idx = 0

        for i, row in enumerate(price_data):
            # Build history up to (but not including) current row
            history = price_data[max(0, i - 252):i]

            if not in_position:
                # Evaluate entry signals — ALL must be True
                if self._check_entry(row, history, entry_signals):
                    in_position = True
                    entry_row = row
                    entry_idx = i
            else:
                # Check exit conditions
                days_held = i - entry_idx
                should_exit = False

                # 1. Exit signals from strategy
                if exit_signals and self._check_exit(
                    row, history, exit_signals
                ):
                    should_exit = True

                # 2. Holding period limit
                if days_held >= holding_limit:
                    should_exit = True

                # 3. Force exit on last bar
                if i == len(price_data) - 1:
                    should_exit = True

                if should_exit and entry_row is not None:
                    trade = self._create_trade(
                        strategy_id=strategy_id,
                        asset=asset,
                        direction=direction,
                        entry_row=entry_row,
                        exit_row=row,
                        days_held=days_held,
                    )
                    trades.append(trade)
                    in_position = False
                    entry_row = None

        logger.info(
            "TradeExecutor generated %d trades for strategy %s.",
            len(trades), strategy_id,
        )
        return trades

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _check_entry(
        row: dict, history: list[dict], signals: list
    ) -> bool:
        """Return True if ALL entry signals fire."""
        if not signals:
            return False
        return all(sig(row, history) for sig in signals)

    @staticmethod
    def _check_exit(
        row: dict, history: list[dict], signals: list
    ) -> bool:
        """Return True if ANY exit signal fires."""
        if not signals:
            return False
        return any(sig(row, history) for sig in signals)

    @staticmethod
    def _create_trade(
        strategy_id: str,
        asset: str,
        direction: str,
        entry_row: dict,
        exit_row: dict,
        days_held: int,
    ) -> dict[str, Any]:
        """Build a trade record dict."""
        entry_price = entry_row.get("close", 0.0)
        exit_price = exit_row.get("close", 0.0)

        # Calculate raw PnL direction
        if direction == "long":
            raw_pnl_pct = (
                (exit_price - entry_price) / entry_price
                if entry_price else 0.0
            )
        else:
            raw_pnl_pct = (
                (entry_price - exit_price) / entry_price
                if entry_price else 0.0
            )

        entry_ts = entry_row.get("date")
        exit_ts = exit_row.get("date")
        # Normalise to datetime if needed
        if isinstance(entry_ts, str):
            entry_ts = datetime.fromisoformat(entry_ts)
        if isinstance(exit_ts, str):
            exit_ts = datetime.fromisoformat(exit_ts)

        return {
            "trade_id": str(uuid.uuid4()),
            "strategy_id": strategy_id,
            "asset": asset,
            "direction": direction,
            "entry_timestamp": entry_ts,
            "exit_timestamp": exit_ts,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "raw_pnl_pct": raw_pnl_pct,
            "holding_period": max(days_held, 1),
        }
