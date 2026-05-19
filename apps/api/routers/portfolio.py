from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from apps.api.middleware.auth import get_current_user

router = APIRouter()


class Position(BaseModel):
    ticker: str
    quantity: float
    avg_cost: float


@router.get("/positions")
async def get_positions(user=Depends(get_current_user)):
    from apps.api.database import AsyncSessionLocal
    from database.models.users import PortfolioPosition
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PortfolioPosition).where(PortfolioPosition.user_id == user.user_id)
        )
        positions = result.scalars().all()
    return [{"ticker": p.ticker, "quantity": p.quantity, "avg_cost": p.avg_cost} for p in positions]


@router.post("/positions", status_code=201)
async def add_position(payload: Position, user=Depends(get_current_user)):
    from apps.api.database import AsyncSessionLocal
    from database.models.users import PortfolioPosition
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PortfolioPosition).where(
                PortfolioPosition.user_id == user.user_id,
                PortfolioPosition.ticker == payload.ticker.upper(),
            )
        )
        pos = result.scalar_one_or_none()
        if pos:
            pos.quantity = payload.quantity
            pos.avg_cost = payload.avg_cost
        else:
            pos = PortfolioPosition(
                user_id=user.user_id,
                ticker=payload.ticker.upper(),
                quantity=payload.quantity,
                avg_cost=payload.avg_cost,
            )
            db.add(pos)
        await db.commit()
    return {"status": "ok"}


@router.get("/analysis")
async def get_portfolio_analysis(user=Depends(get_current_user)):
    """Full AI portfolio risk report."""
    from portfolio.analyzer import analyze_portfolio
    return await analyze_portfolio(str(user.user_id))


@router.get("/risk")
async def get_risk_metrics(user=Depends(get_current_user)):
    """Detailed risk metrics: VaR, beta, correlation."""
    from portfolio.risk_metrics import compute_risk_metrics
    return await compute_risk_metrics(str(user.user_id))


@router.get("/correlation")
async def get_correlation_matrix(user=Depends(get_current_user)):
    """Portfolio correlation heatmap data."""
    from portfolio.correlation import compute_correlation_matrix
    return await compute_correlation_matrix(str(user.user_id))
