"""
Multi-Agent Strategy Competition Runner.

For each ticker in the user's watchlist, 5 independent strategy agents
compete by backtesting on historical data. Results are ranked and an AI
coach interprets which strategies work best for each ticker and why.

Architecture:
  CompetitionOrchestrator
    ├── Agent 1: RSI Mean Reversion
    ├── Agent 2: EMA Trend Following
    ├── Agent 3: Bollinger Breakout
    ├── Agent 4: MACD Momentum
    └── Agent 5: Volume + Price Composite

  Each agent:
    1. Downloads historical data (1 year)
    2. Applies its strategy signal function
    3. Simulates trades with realistic costs
    4. Computes performance metrics
    5. Returns structured result

  Orchestrator:
    1. Runs all 5 agents concurrently per ticker
    2. Ranks strategies by risk-adjusted return (Sharpe)
    3. Calls Claude to interpret results and explain the winner
    4. Returns consolidated competition report
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

from agents.strategy_competition.strategies import STRATEGIES, run_strategy
from intelligence.base import MANDATORY_DISCLAIMER
from apps.api.config import get_settings

settings = get_settings()

COMMISSION_PCT = 0.1 / 100   # 0.1% per trade
SLIPPAGE_PCT   = 0.05 / 100  # 0.05% per trade
MIN_TRADES     = 3


@dataclass
class AgentResult:
    strategy_id: str
    strategy_name: str
    ticker: str
    period: str
    total_trades: int
    win_rate: float
    avg_return_pct: float
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    profit_factor: float
    trades: list[dict] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class CompetitionResult:
    ticker: str
    period: str
    agents: list[AgentResult]
    winner: Optional[str]
    winner_name: Optional[str]
    ranking: list[dict]
    ai_interpretation: str
    disclaimer: str = MANDATORY_DISCLAIMER
    run_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _compute_metrics(trades_list: list) -> dict:
    """Compute performance metrics from a list of Trade objects."""
    if len(trades_list) < MIN_TRADES:
        return {"error": f"Insufficient trades ({len(trades_list)} < {MIN_TRADES})"}

    pnls = np.array([t.pnl_pct - (COMMISSION_PCT + SLIPPAGE_PCT) * 2 * 100 for t in trades_list])

    win_rate = float((pnls > 0).mean())
    avg_return = float(pnls.mean())
    total_return = float(np.prod(1 + pnls / 100) - 1) * 100
    sharpe = float(pnls.mean() / pnls.std() * (252 ** 0.5)) if pnls.std() > 0 else 0.0

    # Max drawdown
    equity = np.cumprod(1 + pnls / 100)
    peak = np.maximum.accumulate(equity)
    drawdowns = (equity - peak) / peak
    max_dd = float(drawdowns.min() * 100)

    # Profit factor
    gains = pnls[pnls > 0].sum()
    losses = abs(pnls[pnls < 0].sum())
    pf = round(gains / losses, 3) if losses > 0 else float("inf")

    return {
        "win_rate": round(win_rate, 3),
        "avg_return_pct": round(avg_return, 3),
        "total_return_pct": round(total_return, 2),
        "sharpe_ratio": round(sharpe, 3),
        "max_drawdown_pct": round(max_dd, 2),
        "profit_factor": pf,
    }


async def run_single_agent(
    strategy_id: str,
    strategy_name: str,
    signal_fn,
    ticker: str,
    hist: pd.DataFrame,
    period: str,
) -> AgentResult:
    """Run one strategy agent on a ticker's historical data."""
    try:
        trades = await asyncio.to_thread(run_strategy, hist, signal_fn)
        if not trades:
            return AgentResult(
                strategy_id=strategy_id, strategy_name=strategy_name,
                ticker=ticker, period=period, total_trades=0, win_rate=0,
                avg_return_pct=0, total_return_pct=0, sharpe_ratio=0,
                max_drawdown_pct=0, profit_factor=0,
                error="No trades generated",
            )

        metrics = _compute_metrics(trades)
        if "error" in metrics:
            return AgentResult(
                strategy_id=strategy_id, strategy_name=strategy_name,
                ticker=ticker, period=period, total_trades=len(trades),
                win_rate=0, avg_return_pct=0, total_return_pct=0,
                sharpe_ratio=0, max_drawdown_pct=0, profit_factor=0,
                error=metrics["error"],
            )

        return AgentResult(
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            ticker=ticker,
            period=period,
            total_trades=len(trades),
            trades=[asdict(t) for t in trades[:10]],  # store last 10
            **metrics,
        )
    except Exception as exc:
        return AgentResult(
            strategy_id=strategy_id, strategy_name=strategy_name,
            ticker=ticker, period=period, total_trades=0, win_rate=0,
            avg_return_pct=0, total_return_pct=0, sharpe_ratio=0,
            max_drawdown_pct=0, profit_factor=0, error=str(exc),
        )


async def _generate_interpretation(
    ticker: str,
    results: list[AgentResult],
    winner: AgentResult,
) -> str:
    """Claude interprets the competition results and explains the winner."""
    results_text = "\n".join(
        f"  {r.strategy_name}: Sharpe={r.sharpe_ratio:.2f}, "
        f"Win Rate={r.win_rate:.1%}, Total Return={r.total_return_pct:.1f}%, "
        f"Trades={r.total_trades}"
        + (f", Error: {r.error}" if r.error else "")
        for r in results
    )

    prompt = f"""You are a quantitative analyst reviewing backtested strategy competition results for {ticker}.

Strategy Results (1-year backtest):
{results_text}

Winner: {winner.strategy_name}
- Sharpe Ratio: {winner.sharpe_ratio:.2f}
- Win Rate: {winner.win_rate:.1%}
- Total Return: {winner.total_return_pct:.1f}%
- Max Drawdown: {winner.max_drawdown_pct:.1f}%
- Trades: {winner.total_trades}

Write a 3-4 sentence analysis explaining:
1. Why the winning strategy worked well for this specific ticker
2. What the losing strategies struggled with
3. What market conditions favor this type of strategy
4. One key caution for a trader using this strategy

Be specific and educational. No buy/sell recommendations."""

    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception:
        return (
            f"{winner.strategy_name} achieved the highest Sharpe ratio ({winner.sharpe_ratio:.2f}) "
            f"for {ticker} with a {winner.win_rate:.1%} win rate over {winner.total_trades} trades. "
            f"Always validate backtest results with forward testing before deployment."
        )


async def run_competition(ticker: str, period: str = "1y") -> CompetitionResult:
    """
    Main entry: run all 5 strategy agents against a ticker.
    Returns a ranked competition result with AI interpretation.
    """
    # Fetch historical data once (shared across all agents)
    try:
        hist = await asyncio.to_thread(
            lambda: yf.Ticker(ticker).history(period=period, interval="1d")
        )
    except Exception as exc:
        return CompetitionResult(
            ticker=ticker, period=period, agents=[], winner=None,
            winner_name=None, ranking=[],
            ai_interpretation=f"Unable to fetch data for {ticker}: {exc}",
        )

    if hist.empty or len(hist) < 50:
        return CompetitionResult(
            ticker=ticker, period=period, agents=[], winner=None,
            winner_name=None, ranking=[],
            ai_interpretation=f"Insufficient historical data for {ticker} (need at least 50 trading days).",
        )

    # Run all agents concurrently
    tasks = [
        run_single_agent(sid, sname, sfn, ticker, hist, period)
        for sid, (sname, sfn) in STRATEGIES.items()
    ]
    results: list[AgentResult] = await asyncio.gather(*tasks)

    # Rank by Sharpe (valid results first)
    valid = [r for r in results if not r.error and r.total_trades >= MIN_TRADES]
    valid.sort(key=lambda r: r.sharpe_ratio, reverse=True)
    all_sorted = valid + [r for r in results if r.error or r.total_trades < MIN_TRADES]

    winner = valid[0] if valid else None
    winner_name = winner.strategy_name if winner else None

    ranking = [
        {
            "rank": i + 1,
            "strategy_id": r.strategy_id,
            "strategy_name": r.strategy_name,
            "sharpe_ratio": r.sharpe_ratio,
            "total_return_pct": r.total_return_pct,
            "win_rate": r.win_rate,
            "total_trades": r.total_trades,
            "max_drawdown_pct": r.max_drawdown_pct,
            "status": "error" if r.error else "ok",
        }
        for i, r in enumerate(all_sorted)
    ]

    # AI interpretation
    interpretation = (
        await _generate_interpretation(ticker, results, winner)
        if winner
        else f"No strategy generated sufficient trades to evaluate for {ticker}."
    )

    return CompetitionResult(
        ticker=ticker,
        period=period,
        agents=[asdict(r) for r in results],
        winner=winner.strategy_id if winner else None,
        winner_name=winner_name,
        ranking=ranking,
        ai_interpretation=interpretation,
    )


async def run_watchlist_competition(
    user_id: str,
    period: str = "1y",
) -> dict:
    """
    Run strategy competition for all tickers in the user's watchlists.
    Returns a summary report with per-ticker winners and an overall recommendation.
    """
    from apps.api.database import AsyncSessionLocal
    from database.models.users import Watchlist
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Watchlist).where(Watchlist.user_id == user_id)
        )
        watchlists = result.scalars().all()

    all_tickers: set[str] = set()
    for wl in watchlists:
        for t in (wl.tickers or []):
            all_tickers.add(t)

    if not all_tickers:
        return {
            "error": "No tickers in watchlist. Add stocks first.",
            "results": [],
        }

    # Run competitions concurrently (with a semaphore to avoid rate limiting)
    sem = asyncio.Semaphore(3)  # max 3 concurrent tickers

    async def run_with_sem(ticker: str):
        async with sem:
            return await run_competition(ticker, period)

    competition_results = await asyncio.gather(
        *[run_with_sem(t) for t in all_tickers]
    )

    # Build summary: which strategy wins most often?
    strategy_wins: dict[str, int] = {}
    for cr in competition_results:
        if cr.winner:
            strategy_wins[cr.winner] = strategy_wins.get(cr.winner, 0) + 1

    overall_winner_id = max(strategy_wins, key=strategy_wins.get) if strategy_wins else None
    overall_winner_name = STRATEGIES[overall_winner_id][0] if overall_winner_id else None

    return {
        "tickers_analyzed": list(all_tickers),
        "period": period,
        "per_ticker": [
            {
                "ticker": cr.ticker,
                "winner": cr.winner_name,
                "winner_sharpe": next((r["sharpe_ratio"] for r in cr.ranking if r["rank"] == 1), None),
                "ranking": cr.ranking,
                "ai_interpretation": cr.ai_interpretation,
            }
            for cr in competition_results
        ],
        "overall_best_strategy": {
            "strategy_id": overall_winner_id,
            "strategy_name": overall_winner_name,
            "wins": strategy_wins.get(overall_winner_id, 0),
            "total_tickers": len(all_tickers),
        },
        "strategy_win_counts": strategy_wins,
        "disclaimer": MANDATORY_DISCLAIMER,
        "run_at": datetime.now(timezone.utc).isoformat(),
    }
