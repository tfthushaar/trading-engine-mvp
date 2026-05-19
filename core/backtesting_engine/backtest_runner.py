"""
Backtest Runner — orchestrates a single strategy backtest end-to-end:

1. Interpret strategy conditions
2. Fetch historical price data
3. Execute trades
4. Simulate portfolio
5. Compute performance metrics
6. Compare to benchmark

Also applies validation: rejects strategies with fewer than the
minimum number of trades or unrealistic leverage.
"""

from __future__ import annotations

import uuid

from typing import Any

from backtesting_engine.strategy_interpreter import StrategyInterpreter
from backtesting_engine.trade_executor import TradeExecutor
from backtesting_engine.portfolio_simulator import PortfolioSimulator
from backtesting_engine.performance_metrics import PerformanceMetrics
from backtesting_engine.benchmark_comparison import BenchmarkComparison

from utils.config import BACKTEST_MIN_TRADES
from utils.logger import get_logger

logger = get_logger(__name__)


class BacktestRunner:
    """Run a complete backtest for a single trading strategy."""

    def __init__(self) -> None:
        self.interpreter = StrategyInterpreter()
        self.executor = TradeExecutor()
        self.simulator = PortfolioSimulator()
        self.metrics = PerformanceMetrics()
        self.benchmark = BenchmarkComparison()

    def run(
        self,
        strategy: dict[str, Any],
        db,
    ) -> dict[str, Any] | None:
        """Execute full backtest pipeline for one strategy.

        Parameters
        ----------
        strategy
            Strategy dict from ``trading_strategies`` table.
        db
            ``DatabaseManager`` instance.

        Returns
        -------
        dict | None
            Complete backtest result (ready for DB insertion) or None
            if the strategy was rejected.
        """
        sid = strategy.get("strategy_id", "unknown")
        sname = strategy.get("strategy_name", "")

        logger.info("Starting backtest for '%s' (%s).", sname, sid)

        # 1 — Interpret strategy
        interpreted = self.interpreter.interpret(strategy)
        if interpreted is None:
            logger.warning("Cannot interpret strategy '%s'. Skipping.", sname)
            return None

        # 2 — Fetch historical price data
        asset = interpreted["asset"]
        price_data = db.fetch_stock_prices_for_backtest(ticker=asset)

        if len(price_data) < 30:
            logger.warning(
                "Insufficient price data for '%s' (%d rows). "
                "Trying SPY fallback.",
                asset, len(price_data),
            )
            if asset != "SPY":
                price_data = db.fetch_stock_prices_for_backtest(ticker="SPY")
                asset = "SPY"
                interpreted["asset"] = asset

        if len(price_data) < 30:
            logger.warning(
                "Still insufficient data (%d rows). Skipping '%s'.",
                len(price_data), sname,
            )
            return None

        # Date range
        start_date = price_data[0].get("date")
        end_date = price_data[-1].get("date")

        # 3 — Execute trades
        trades = self.executor.execute(price_data, interpreted, sid)

        # 4 — Validate minimum trades
        if len(trades) < BACKTEST_MIN_TRADES:
            logger.info(
                "Strategy '%s' produced only %d trades (min %d). Rejected.",
                sname, len(trades), BACKTEST_MIN_TRADES,
            )
            return {
                "status": "rejected",
                "reason": f"too_few_trades ({len(trades)})",
                "strategy_id": sid,
                "backtest_id": str(uuid.uuid4()),
                "trades": [],
                "metrics": {},
                "benchmark": {},
                "start_date": start_date,
                "end_date": end_date,
            }

        # 5 — Simulate portfolio
        sim_result = self.simulator.simulate(trades, interpreted)
        final_trades = sim_result["final_trades"]

        # 6 — Validate: check for unrealistic leverage
        if self._has_unrealistic_leverage(sim_result):
            logger.info(
                "Strategy '%s' shows unrealistic leverage. Rejected.", sname,
            )
            return {
                "status": "rejected",
                "reason": "unrealistic_leverage",
                "strategy_id": sid,
                "backtest_id": str(uuid.uuid4()),
                "trades": [],
                "metrics": {},
                "benchmark": {},
                "start_date": start_date,
                "end_date": end_date,
            }

        # 7 — Compute performance metrics
        perf = self.metrics.compute(
            equity_curve=sim_result["equity_curve"],
            daily_returns=sim_result["daily_returns"],
            trades=final_trades,
            start_date=start_date,
            end_date=end_date,
        )

        # 8 — Benchmark comparison
        bench = self.benchmark.compare(
            db=db,
            strategy_return=perf["total_return"],
            start_date=start_date,
            end_date=end_date,
        )

        backtest_id = str(uuid.uuid4())

        result = {
            "status": "completed",
            "strategy_id": sid,
            "backtest_id": backtest_id,
            "start_date": start_date,
            "end_date": end_date,
            "trades": final_trades,
            "metrics": perf,
            "benchmark": bench,
        }

        # 9 — Generate Explainability Insights
        from explainability_engine.strategy_explainer import StrategyExplainer
        explainer = StrategyExplainer(db)
        explanation = explainer.generate_explanation(result)
        if explanation:
            result["explanation"] = explanation

        return result


    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _has_unrealistic_leverage(sim_result: dict) -> bool:
        """Check if the simulation implies unrealistic leverage."""
        equity = sim_result.get("equity_curve", [])
        if len(equity) < 2:
            return False
        initial = equity[0]
        # Flag if any point shows >10x gain or >99% loss
        for val in equity:
            if initial > 0:
                ratio = val / initial
                if ratio > 10.0 or ratio < 0.01:
                    return True
        return False
