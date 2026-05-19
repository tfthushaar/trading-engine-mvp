from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
import uuid

from apps.api.middleware.auth import get_current_user

router = APIRouter()


class StrategyRule(BaseModel):
    indicator: str
    operator: str
    value: float | str
    timeperiod: Optional[int] = None


class UserStrategyRequest(BaseModel):
    strategy_name: str
    entry_conditions: list[StrategyRule]
    exit_conditions: list[StrategyRule]
    stop_loss_pct: float = 5.0
    target_pct: float = 10.0
    asset_scope: list[str] = []
    based_on_template: Optional[str] = None


class BacktestRequest(BaseModel):
    strategy_id: str
    tickers: list[str]
    start_date: str
    end_date: str
    initial_capital: float = 100000.0
    commission_pct: float = 0.1
    slippage_pct: float = 0.05


class MonteCarloRequest(BaseModel):
    strategy_id: str
    n_simulations: int = 10000
    n_periods: int = 252


@router.get("/templates")
async def get_strategy_templates():
    """Return the 5 canonical strategy templates from the existing engine."""
    from core.strategy_engine.strategy_templates import STRATEGY_TEMPLATES
    return {"templates": list(STRATEGY_TEMPLATES.keys())}


@router.post("/strategies", status_code=201)
async def create_strategy(
    payload: UserStrategyRequest,
    user=Depends(get_current_user),
):
    """Save a user-defined strategy."""
    from apps.api.database import AsyncSessionLocal
    from database.models.users import UserStrategy
    async with AsyncSessionLocal() as db:
        strategy = UserStrategy(
            user_id=user.user_id,
            strategy_name=payload.strategy_name,
            based_on_template=payload.based_on_template,
            entry_conditions=[c.model_dump() for c in payload.entry_conditions],
            exit_conditions=[c.model_dump() for c in payload.exit_conditions],
            risk_rules={"stop_loss_pct": payload.stop_loss_pct, "target_pct": payload.target_pct},
            asset_scope=payload.asset_scope,
        )
        db.add(strategy)
        await db.commit()
        await db.refresh(strategy)
    return {"strategy_id": str(strategy.user_strategy_id), "name": strategy.strategy_name}


@router.get("/strategies")
async def list_user_strategies(user=Depends(get_current_user)):
    """List strategies owned by the current user."""
    from apps.api.database import AsyncSessionLocal
    from database.models.users import UserStrategy
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(UserStrategy).where(UserStrategy.user_id == user.user_id)
        )
        strategies = result.scalars().all()
    return [{"id": str(s.user_strategy_id), "name": s.strategy_name} for s in strategies]


@router.post("/backtest")
async def run_backtest(payload: BacktestRequest, user=Depends(get_current_user)):
    """Run backtest on a user strategy (Celery async task)."""
    from apps.api.celery_app import celery_app
    task = celery_app.send_task(
        "apps.api.tasks.intelligence_tasks.run_backtest",
        args=[payload.model_dump(), str(user.user_id)],
    )
    return {"task_id": task.id, "status": "queued"}


@router.get("/backtest/{task_id}/status")
async def get_backtest_status(task_id: str):
    from apps.api.celery_app import celery_app
    from celery.result import AsyncResult
    result = AsyncResult(task_id, app=celery_app)
    return {"task_id": task_id, "status": result.status, "result": result.result if result.ready() else None}


@router.post("/monte-carlo")
async def run_monte_carlo(payload: MonteCarloRequest, user=Depends(get_current_user)):
    """Monte Carlo risk simulation for a strategy."""
    from portfolio.monte_carlo import run_monte_carlo
    return await run_monte_carlo(payload.strategy_id, payload.n_simulations, payload.n_periods)
