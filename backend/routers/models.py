"""Neural-network endpoints: pretrained ensemble signals, model card, and the live training Lab."""
from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from backend.config import get_settings
from backend.dl import global_model
from backend.dl.architectures import ARCHITECTURES
from backend.dl.data import DEFAULT_FEATURES, FEATURES
from backend.dl.pipeline import LAB_INTERVALS, run_experiment
from backend.dl.train import TrainConfig
from backend.http import limit, ok

router = APIRouter(prefix="/api", tags=["models"])


@router.get("/signals/scan")
async def scan(symbols: str | None = Query(None, description="Comma-separated; defaults to the model universe")):
    syms = [s for s in symbols.split(",") if s.strip()][:60] if symbols else None
    return ok(await run_in_threadpool(global_model.scan, syms, 8), cache_s=120)


@router.get("/signals/{symbol}")
async def signal(symbol: str, lookback: int = Query(120, ge=20, le=250)):
    try:
        return ok(await run_in_threadpool(global_model.symbol_detail, symbol, lookback), cache_s=120)
    except global_model.NotScorable as exc:
        return ok({"symbol": symbol.upper(), "supported": False, "reason": str(exc)}, cache_s=300)


@router.get("/models/card")
async def model_card():
    card = await run_in_threadpool(global_model.card)
    return ok({k: v for k, v in card.items() if k not in ("mean", "std")}, cache_s=3600)


@router.get("/lab/options")
async def lab_options():
    return ok({
        "architectures": ARCHITECTURES,
        "features": FEATURES,
        "default_features": DEFAULT_FEATURES,
        "intervals": LAB_INTERVALS,
        "train_defaults": TrainConfig().__dict__,
        "tasks": {"classification": "Direction: P(price higher after the horizon)", "regression": "Magnitude: forward log return"},
    }, cache_s=3600)


class TrainRequest(BaseModel):
    symbol: str = "SPY"
    interval: str = "1d"
    period: str = "10y"
    task: str = "classification"
    arch: str = "lstm"
    arch_params: dict = Field(default_factory=dict)
    features: list[str] | None = None
    window: int = 30
    horizon: int = 5
    threshold: float = 0.5
    cost_bps: float = 5.0
    long_short: bool = False
    baseline: bool = True
    train: dict = Field(default_factory=dict)


@router.post("/lab/train")
async def lab_train(req: TrainRequest):
    limit("train", get_settings().train_per_ip_10min)
    result = await run_in_threadpool(run_experiment, req.model_dump())
    return ok(result)
