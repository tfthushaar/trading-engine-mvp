"""
Performance Metrics — computes strategy performance statistics from
an equity curve and list of completed trades.

Metrics calculated:
- Total return
- Annualized return
- Sharpe ratio
- Maximum drawdown
- Win rate
- Profit factor
- Portfolio volatility (annualized)
- Number of trades
"""

from __future__ import annotations

import math
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)

# Risk-free rate default (annualized)
DEFAULT_RISK_FREE_RATE = 0.05


class PerformanceMetrics:
    """Compute performance statistics from backtest results."""

    def __init__(
        self, risk_free_rate: float = DEFAULT_RISK_FREE_RATE
    ) -> None:
        self.risk_free_rate = risk_free_rate

    def compute(
        self,
        equity_curve: list[float],
        daily_returns: list[float],
        trades: list[dict[str, Any]],
        start_date: Any = None,
        end_date: Any = None,
    ) -> dict[str, Any]:
        """Calculate all performance metrics.

        Parameters
        ----------
        equity_curve
            List of portfolio values over time.
        daily_returns
            List of per-trade return fractions.
        trades
            Finalised trade dicts with PnL.
        start_date / end_date
            Backtest date range for annualisation.

        Returns
        -------
        dict
            Performance summary with all metrics.
        """
        initial = equity_curve[0] if equity_curve else 1.0
        final = equity_curve[-1] if equity_curve else 1.0

        total_return = (final - initial) / initial if initial else 0.0
        n_trades = len(trades)

        # Annualised return
        ann_return = self._annualized_return(
            total_return, start_date, end_date
        )

        # Sharpe ratio
        sharpe = self._sharpe_ratio(daily_returns)

        # Max drawdown
        max_dd = self._max_drawdown(equity_curve)

        # Win rate
        win_rate = self._win_rate(trades)

        # Profit factor
        pf = self._profit_factor(trades)

        # Volatility (annualized)
        vol = self._volatility(daily_returns)

        metrics = {
            "total_return": round(total_return, 6),
            "annualized_return": round(ann_return, 6),
            "sharpe_ratio": round(sharpe, 4),
            "max_drawdown": round(max_dd, 6),
            "win_rate": round(win_rate, 4),
            "profit_factor": round(pf, 4),
            "number_of_trades": n_trades,
            "volatility": round(vol, 6),
        }

        logger.info(
            "Performance: return=%.2f%%, Sharpe=%.2f, "
            "drawdown=%.2f%%, win_rate=%.1f%%, trades=%d",
            total_return * 100, sharpe, max_dd * 100,
            win_rate * 100, n_trades,
        )
        return metrics

    # ------------------------------------------------------------------
    # Individual metric calculations
    # ------------------------------------------------------------------
    def _annualized_return(
        self, total_return: float, start_date: Any, end_date: Any
    ) -> float:
        """Annualise total return based on date range."""
        try:
            from datetime import datetime

            if isinstance(start_date, str):
                start_date = datetime.fromisoformat(start_date).date()
            if isinstance(end_date, str):
                end_date = datetime.fromisoformat(end_date).date()
            if hasattr(start_date, "date"):
                start_date = start_date.date()
            if hasattr(end_date, "date"):
                end_date = end_date.date()

            if start_date and end_date:
                days = (end_date - start_date).days
                if days > 0:
                    years = days / 365.25
                    if total_return > -1:
                        return (1 + total_return) ** (1 / years) - 1
        except Exception:
            pass

        # Fallback: assume ~1 year
        return total_return

    def _sharpe_ratio(self, returns: list[float]) -> float:
        """Compute annualized Sharpe ratio from per-trade returns."""
        if len(returns) < 2:
            return 0.0

        mean_ret = sum(returns) / len(returns)
        variance = sum((r - mean_ret) ** 2 for r in returns) / (
            len(returns) - 1
        )
        std = math.sqrt(variance) if variance > 0 else 0.0

        if std == 0:
            return 0.0

        # Annualise: assume ~252 / avg_trades_per_year
        # Use sqrt(N) scaling where N = number of trades
        trades_per_year = min(len(returns), 252)
        annual_factor = math.sqrt(trades_per_year)
        excess_return = mean_ret - (self.risk_free_rate / trades_per_year)

        return (excess_return / std) * annual_factor

    @staticmethod
    def _max_drawdown(equity_curve: list[float]) -> float:
        """Compute maximum drawdown from peak."""
        if len(equity_curve) < 2:
            return 0.0

        peak = equity_curve[0]
        max_dd = 0.0

        for val in equity_curve:
            if val > peak:
                peak = val
            if peak > 0:
                dd = (peak - val) / peak
                max_dd = max(max_dd, dd)

        return max_dd

    @staticmethod
    def _win_rate(trades: list[dict[str, Any]]) -> float:
        """Fraction of trades with positive PnL."""
        if not trades:
            return 0.0
        wins = sum(1 for t in trades if t.get("pnl", 0) > 0)
        return wins / len(trades)

    @staticmethod
    def _profit_factor(trades: list[dict[str, Any]]) -> float:
        """Gross profit / gross loss.  Returns inf if no losses."""
        gross_profit = sum(
            t.get("pnl", 0) for t in trades if t.get("pnl", 0) > 0
        )
        gross_loss = abs(sum(
            t.get("pnl", 0) for t in trades if t.get("pnl", 0) < 0
        ))
        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0
        return gross_profit / gross_loss

    @staticmethod
    def _volatility(returns: list[float]) -> float:
        """Annualized portfolio volatility."""
        if len(returns) < 2:
            return 0.0
        mean_ret = sum(returns) / len(returns)
        variance = sum((r - mean_ret) ** 2 for r in returns) / (
            len(returns) - 1
        )
        std = math.sqrt(variance) if variance > 0 else 0.0
        # Annualise
        trades_per_year = min(len(returns), 252)
        return std * math.sqrt(trades_per_year)
