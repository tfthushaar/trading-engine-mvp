"""
Backtesting Engine — Phase 5.

Automated backtest runner that evaluates validated trading strategies
against historical market data, computes performance metrics, and
stores results in DuckDB.
"""

from backtesting_engine.strategy_interpreter import StrategyInterpreter
from backtesting_engine.trade_executor import TradeExecutor
from backtesting_engine.portfolio_simulator import PortfolioSimulator
from backtesting_engine.performance_metrics import PerformanceMetrics
from backtesting_engine.benchmark_comparison import BenchmarkComparison
from backtesting_engine.backtest_runner import BacktestRunner

__all__ = [
    "StrategyInterpreter",
    "TradeExecutor",
    "PortfolioSimulator",
    "PerformanceMetrics",
    "BenchmarkComparison",
    "BacktestRunner",
    "BacktestEngine",
]


class BacktestEngine:
    """Top-level orchestrator for the Automated Backtesting Engine.

    Pipeline:
    1. Fetch validated strategies from trading_strategies
    2. Run each through BacktestRunner (interpret → trade → simulate → metrics)
    3. Compute composite performance_score
    4. Store results in backtest_results, trade_logs, strategy_performance
    5. Update strategy status to 'backtested' or 'promoted'
    """

    # Scoring weights for composite performance_score
    WEIGHT_SHARPE = 0.40
    WEIGHT_DRAWDOWN = 0.25
    WEIGHT_CONSISTENCY = 0.20
    WEIGHT_BENCHMARK = 0.15

    def __init__(self, db, **kwargs) -> None:
        from database.db_manager import DatabaseManager

        self.db: DatabaseManager = db
        self.runner = BacktestRunner()

    def run(self) -> dict:
        """Execute one backtesting cycle for all un-backtested strategies.

        Returns
        -------
        dict
            Summary with counts at each stage.
        """
        from datetime import datetime
        from utils.logger import get_logger

        logger = get_logger(__name__)
        start = datetime.utcnow()

        logger.info("=" * 60)
        logger.info(
            "Backtesting engine starting at %s", start.isoformat()
        )
        logger.info("=" * 60)

        # Ensure schema exists
        self.db.initialize()

        # 1 — Fetch validated strategies
        logger.info("[Backtest 1/4] Fetching validated strategies …")
        strategies = self.db.fetch_validated_strategies()
        if not strategies:
            logger.info("No un-backtested strategies found. Nothing to do.")
            return {"strategies_found": 0, "backtests_completed": 0}

        # 2 — Run backtests
        logger.info(
            "[Backtest 2/4] Running backtests for %d strategies …",
            len(strategies),
        )
        results: list[dict] = []
        rejected = 0
        for s in strategies:
            result = self.runner.run(s, self.db)
            if result is None:
                rejected += 1
                continue
            if result.get("status") == "rejected":
                rejected += 1
                self._store_rejected(result)
                self.db.update_strategy_status(
                    result["strategy_id"], "rejected"
                )
                continue
            results.append(result)

        # 3 — Score and persist
        logger.info(
            "[Backtest 3/4] Scoring and persisting %d results …",
            len(results),
        )
        for result in results:
            self._score_and_persist(result)

        # 4 — Summary
        elapsed = (datetime.utcnow() - start).total_seconds()
        summary = {
            "strategies_found": len(strategies),
            "backtests_completed": len(results),
            "rejected": rejected,
            "elapsed_seconds": elapsed,
        }

        logger.info("-" * 60)
        logger.info("Backtesting complete in %.1f s", elapsed)
        logger.info("  Strategies found:      %d", summary["strategies_found"])
        logger.info("  Backtests completed:   %d", summary["backtests_completed"])
        logger.info("  Rejected:              %d", summary["rejected"])
        logger.info("=" * 60)

        return summary

    # ------------------------------------------------------------------
    # Scoring & persistence
    # ------------------------------------------------------------------
    def _score_and_persist(self, result: dict) -> None:
        """Compute composite score and store all results."""
        metrics = result.get("metrics", {})
        bench = result.get("benchmark", {})
        trades = result.get("trades", [])
        sid = result["strategy_id"]
        bid = result["backtest_id"]

        # Compute composite scores
        sharpe = metrics.get("sharpe_ratio", 0.0)
        max_dd = metrics.get("max_drawdown", 1.0)
        win_rate = metrics.get("win_rate", 0.0)
        outperformance = bench.get("outperformance", 0.0)

        # Normalise each component to 0-1 scale
        sharpe_score = min(max(sharpe / 3.0, 0.0), 1.0)
        dd_score = max(1.0 - max_dd / 0.3, 0.0)  # 30% DD → 0
        consistency_score = win_rate  # Win rate is already 0-1
        bench_score = min(
            max((outperformance + 0.1) / 0.3, 0.0), 1.0
        )

        performance_score = (
            self.WEIGHT_SHARPE * sharpe_score
            + self.WEIGHT_DRAWDOWN * dd_score
            + self.WEIGHT_CONSISTENCY * consistency_score
            + self.WEIGHT_BENCHMARK * bench_score
        )

        # Build evaluation notes
        notes = (
            f"Sharpe={sharpe:.2f}, DD={max_dd:.1%}, "
            f"WinRate={win_rate:.1%}, "
            f"BenchOut={outperformance:.2%}"
        )

        # Determine promotion
        promoted = performance_score >= 0.5 and sharpe > 0.5

        # Store backtest_results
        self.db.insert_backtest_results([{
            "backtest_id": bid,
            "strategy_id": sid,
            "start_date": result.get("start_date"),
            "end_date": result.get("end_date"),
            "total_return": metrics.get("total_return"),
            "annualized_return": metrics.get("annualized_return"),
            "sharpe_ratio": sharpe,
            "max_drawdown": max_dd,
            "win_rate": win_rate,
            "profit_factor": metrics.get("profit_factor"),
            "number_of_trades": metrics.get("number_of_trades"),
            "volatility": metrics.get("volatility"),
            "status": "promoted" if promoted else "completed",
        }])

        # Store trade_logs
        if trades:
            self.db.insert_trade_logs(trades)

        # Store strategy_performance
        self.db.insert_strategy_performance([{
            "strategy_id": sid,
            "backtest_id": bid,
            "performance_score": round(performance_score, 4),
            "risk_score": round(dd_score, 4),
            "consistency_score": round(consistency_score, 4),
            "benchmark_outperformance": outperformance,
            "evaluation_notes": notes,
        }])

        # Store explanation if present
        explanation = result.get("explanation")
        if explanation:
            self.db.insert_strategy_explanations([explanation])

        # Update strategy status
        new_status = "promoted" if promoted else "backtested"
        self.db.update_strategy_status(sid, new_status)

    def _store_rejected(self, result: dict) -> None:
        """Store a minimal backtest record for a rejected strategy."""
        self.db.insert_backtest_results([{
            "backtest_id": result.get("backtest_id"),
            "strategy_id": result.get("strategy_id"),
            "start_date": result.get("start_date"),
            "end_date": result.get("end_date"),
            "total_return": None,
            "annualized_return": None,
            "sharpe_ratio": None,
            "max_drawdown": None,
            "win_rate": None,
            "profit_factor": None,
            "number_of_trades": 0,
            "volatility": None,
            "status": f"rejected: {result.get('reason', 'unknown')}",
        }])
