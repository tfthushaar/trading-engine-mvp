"""
Portfolio Simulator — simulates portfolio execution with realistic
constraints: position sizing, transaction costs, slippage, and
stop-loss / take-profit enforcement.

Tracks the equity curve and produces finalised trade records with
actual PnL after costs.
"""

from __future__ import annotations


from typing import Any

from utils.config import (
    BACKTEST_INITIAL_CAPITAL,
    BACKTEST_TRANSACTION_COST_PCT,
    BACKTEST_SLIPPAGE_PCT,
)
from utils.logger import get_logger

logger = get_logger(__name__)


class PortfolioSimulator:
    """Simulate portfolio execution for a list of trades."""

    def __init__(
        self,
        initial_capital: float | None = None,
        transaction_cost_pct: float | None = None,
        slippage_pct: float | None = None,
    ) -> None:
        self.initial_capital = initial_capital or BACKTEST_INITIAL_CAPITAL
        self.transaction_cost = (
            transaction_cost_pct
            if transaction_cost_pct is not None
            else BACKTEST_TRANSACTION_COST_PCT
        )
        self.slippage = (
            slippage_pct
            if slippage_pct is not None
            else BACKTEST_SLIPPAGE_PCT
        )

    def simulate(
        self,
        trades: list[dict[str, Any]],
        interpreted: dict[str, Any],
    ) -> dict[str, Any]:
        """Run portfolio simulation over trade list.

        Parameters
        ----------
        trades
            Raw trades from ``TradeExecutor``.
        interpreted
            Interpreted strategy from ``StrategyInterpreter``.

        Returns
        -------
        dict
            Keys: final_trades, equity_curve, daily_returns,
                  final_capital, total_return.
        """
        if not trades:
            return {
                "final_trades": [],
                "equity_curve": [self.initial_capital],
                "daily_returns": [],
                "final_capital": self.initial_capital,
                "total_return": 0.0,
            }

        stop_loss_pct = interpreted.get("stop_loss_pct", 5.0)
        take_profit_pct = interpreted.get("take_profit_pct")
        position_sizing = interpreted.get("position_sizing", {})
        direction = interpreted.get("direction", "long")

        capital = self.initial_capital
        equity_curve = [capital]
        daily_returns: list[float] = []
        final_trades: list[dict[str, Any]] = []

        for trade in trades:
            # Determine position size
            pos_size = self._calculate_position_size(
                capital, position_sizing, trade
            )
            if pos_size <= 0:
                continue

            entry_price = trade["entry_price"]
            exit_price = trade["exit_price"]

            if entry_price <= 0:
                continue

            # Apply slippage to entry and exit
            if direction == "long":
                adj_entry = entry_price * (1 + self.slippage)
                adj_exit = exit_price * (1 - self.slippage)
            else:
                adj_entry = entry_price * (1 - self.slippage)
                adj_exit = exit_price * (1 + self.slippage)

            # Enforce stop-loss
            if direction == "long":
                stop_price = adj_entry * (1 - stop_loss_pct / 100.0)
                if adj_exit < stop_price:
                    adj_exit = stop_price
            else:
                stop_price = adj_entry * (1 + stop_loss_pct / 100.0)
                if adj_exit > stop_price:
                    adj_exit = stop_price

            # Enforce take-profit
            if take_profit_pct is not None:
                if direction == "long":
                    tp_price = adj_entry * (1 + take_profit_pct / 100.0)
                    if adj_exit > tp_price:
                        adj_exit = tp_price
                else:
                    tp_price = adj_entry * (1 - take_profit_pct / 100.0)
                    if adj_exit < tp_price:
                        adj_exit = tp_price

            # Calculate shares and PnL
            shares = pos_size / adj_entry
            if direction == "long":
                gross_pnl = shares * (adj_exit - adj_entry)
            else:
                gross_pnl = shares * (adj_entry - adj_exit)

            # Transaction costs (on entry + exit notional)
            cost = (pos_size + shares * adj_exit) * self.transaction_cost
            net_pnl = gross_pnl - cost

            # Update capital
            capital += net_pnl
            equity_curve.append(capital)

            # Daily return for this trade period
            if equity_curve[-2] > 0:
                ret = net_pnl / equity_curve[-2]
            else:
                ret = 0.0
            daily_returns.append(ret)

            # Finalise trade record
            final_trade = {
                **trade,
                "position_size": pos_size,
                "entry_price": adj_entry,
                "exit_price": adj_exit,
                "pnl": round(net_pnl, 2),
                "holding_period": trade.get("holding_period", 1),
            }
            final_trades.append(final_trade)

        total_return = (
            (capital - self.initial_capital) / self.initial_capital
            if self.initial_capital > 0
            else 0.0
        )

        logger.info(
            "Portfolio simulation: %d trades, final capital $%.2f, "
            "total return %.2f%%.",
            len(final_trades), capital, total_return * 100,
        )

        return {
            "final_trades": final_trades,
            "equity_curve": equity_curve,
            "daily_returns": daily_returns,
            "final_capital": capital,
            "total_return": total_return,
        }

    # ------------------------------------------------------------------
    # Position sizing
    # ------------------------------------------------------------------
    def _calculate_position_size(
        self,
        capital: float,
        sizing_rules: dict | list,
        trade: dict,
    ) -> float:
        """Determine dollar amount to allocate to a trade."""
        if isinstance(sizing_rules, list):
            sizing_rules = sizing_rules[0] if sizing_rules else {}
        if not isinstance(sizing_rules, dict):
            sizing_rules = {}

        method = str(sizing_rules.get("method", "equal_weight")).lower()
        max_pct = float(sizing_rules.get("max_position_pct", 10.0))
        max_pos = capital * (max_pct / 100.0)

        if method in ("equal_weight", "equal"):
            pos = capital * (max_pct / 100.0)
        elif method in ("volatility_adjusted", "volatility"):
            # Use a simpler fixed percentage as proxy
            target_vol = float(
                sizing_rules.get("target_volatility_pct", 15.0)
            )
            pos = capital * min(target_vol / 100.0, max_pct / 100.0)
        elif method in ("conviction_weighted", "conviction"):
            base_pct = float(sizing_rules.get("base_position_pct", 5.0))
            pos = capital * (base_pct / 100.0)
        elif method in ("risk_per_trade", "risk_parity"):
            risk_pct = float(sizing_rules.get("risk_per_trade_pct", 1.0))
            pos = capital * (risk_pct / 100.0) * 10  # ~10:1 risk/reward
        else:
            pos = capital * 0.05  # 5% default

        return min(pos, max_pos, capital * 0.2)  # Hard cap at 20%
