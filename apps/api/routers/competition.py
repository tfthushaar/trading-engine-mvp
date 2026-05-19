"""
Strategy competition API routes.
Runs 5 strategy agents against watchlist tickers and ranks results.
"""
from fastapi import APIRouter, Depends, Query
from apps.api.middleware.auth import get_current_user

router = APIRouter()


@router.post("/run/{ticker}")
async def run_ticker_competition(
    ticker: str,
    period: str = Query("1y", description="1y | 6mo | 2y"),
):
    """
    Run all 5 strategy agents against a single ticker.
    Returns ranked results with AI interpretation.
    """
    from agents.strategy_competition.competition_runner import run_competition
    result = await run_competition(ticker.upper(), period)
    return result


@router.post("/run-watchlist")
async def run_watchlist_competition(
    period: str = Query("1y"),
    user=Depends(get_current_user),
):
    """
    Run strategy competition for all tickers in user's watchlists.
    Returns per-ticker winners and overall best strategy.
    """
    from agents.strategy_competition.competition_runner import run_watchlist_competition
    return await run_watchlist_competition(str(user.user_id), period)


@router.get("/strategies")
async def list_strategies():
    """List all available strategy agents."""
    from agents.strategy_competition.strategies import STRATEGIES
    return {
        "strategies": [
            {"id": sid, "name": sname}
            for sid, (sname, _) in STRATEGIES.items()
        ]
    }


@router.post("/run-async")
async def run_competition_async(
    tickers: list[str],
    period: str = Query("1y"),
    user=Depends(get_current_user),
):
    """Queue competition as a Celery task for large watchlists."""
    from apps.api.celery_app import celery_app
    task = celery_app.send_task(
        "apps.api.tasks.competition_tasks.run_competition_task",
        args=[tickers, period, str(user.user_id)],
    )
    return {"task_id": task.id, "status": "queued", "tickers": tickers}
