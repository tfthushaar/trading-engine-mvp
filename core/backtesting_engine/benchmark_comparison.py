"""
Benchmark Comparison — compares strategy returns against a benchmark
index (S&P 500 by default) over the matching date range.

Uses price data already stored in ``stock_prices`` to compute
benchmark buy-and-hold return, then calculates outperformance.
"""

from __future__ import annotations

from typing import Any

from utils.config import BACKTEST_BENCHMARK_TICKER
from utils.logger import get_logger

logger = get_logger(__name__)


class BenchmarkComparison:
    """Compute benchmark-relative performance for a backtested strategy."""

    def __init__(
        self, benchmark_ticker: str | None = None
    ) -> None:
        self.benchmark_ticker = benchmark_ticker or BACKTEST_BENCHMARK_TICKER

    def compare(
        self,
        db,
        strategy_return: float,
        start_date: Any,
        end_date: Any,
    ) -> dict[str, Any]:
        """Compare strategy return against benchmark.

        Parameters
        ----------
        db
            ``DatabaseManager`` instance.
        strategy_return
            Total return of the strategy (as a fraction, e.g. 0.15).
        start_date / end_date
            Backtest date range.

        Returns
        -------
        dict
            benchmark_ticker, benchmark_return, outperformance.
        """
        benchmark_data = db.fetch_stock_prices_for_backtest(
            ticker=self.benchmark_ticker,
            start_date=str(start_date) if start_date else None,
            end_date=str(end_date) if end_date else None,
        )

        if len(benchmark_data) < 2:
            logger.warning(
                "Insufficient benchmark data for '%s' (%d rows). "
                "Falling back to 0%% benchmark.",
                self.benchmark_ticker, len(benchmark_data),
            )
            return {
                "benchmark_ticker": self.benchmark_ticker,
                "benchmark_return": 0.0,
                "outperformance": strategy_return,
            }

        first_close = benchmark_data[0].get("close", 0)
        last_close = benchmark_data[-1].get("close", 0)

        if first_close and first_close > 0:
            benchmark_return = (last_close - first_close) / first_close
        else:
            benchmark_return = 0.0

        outperformance = strategy_return - benchmark_return

        logger.info(
            "Benchmark '%s': return=%.2f%%, strategy outperformance=%.2f%%.",
            self.benchmark_ticker,
            benchmark_return * 100,
            outperformance * 100,
        )

        return {
            "benchmark_ticker": self.benchmark_ticker,
            "benchmark_return": round(benchmark_return, 6),
            "outperformance": round(outperformance, 6),
        }
