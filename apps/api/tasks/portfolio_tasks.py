"""Celery tasks for portfolio analysis."""
import asyncio
from apps.api.celery_app import celery_app


@celery_app.task(name="apps.api.tasks.portfolio_tasks.refresh_portfolio_snapshots")
def refresh_portfolio_snapshots() -> dict:
    """Nightly: recompute portfolio risk snapshots for all users with positions."""
    try:
        result = asyncio.run(_async_refresh())
        return result
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


async def _async_refresh() -> dict:
    from apps.api.database import AsyncSessionLocal
    from database.models.users import PortfolioPosition, PortfolioRiskSnapshot
    from portfolio.analyzer import analyze_portfolio
    from sqlalchemy import select
    from datetime import datetime, timezone

    # Get distinct users with positions
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(PortfolioPosition.user_id).distinct())
        user_ids = [str(r[0]) for r in result.fetchall()]

    refreshed = 0
    for uid in user_ids:
        try:
            analysis = await analyze_portfolio(uid)
            if analysis.get("health_score"):
                refreshed += 1
        except Exception:
            pass

    return {"status": "ok", "users_refreshed": refreshed}
