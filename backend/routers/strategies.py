"""Rule-strategy endpoints: built-in strategy comparison, no-code rule backtests, Monte Carlo."""
from __future__ import annotations

import numpy as np
from fastapi import APIRouter
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from backend.ai import llm
from backend.http import limit, ok
from backend.market import data as md
from backend.strategies import engine, montecarlo, rules

router = APIRouter(prefix="/api/strategies", tags=["strategies"])
INTERVALS = {"1h": ["1mo", "3mo", "6mo", "1y", "2y"], "1d": ["1y", "2y", "5y", "10y", "max"], "1wk": ["5y", "10y", "max"]}


def _load(symbol: str, period: str, interval: str):
    if interval not in INTERVALS:
        raise ValueError(f"interval must be one of {', '.join(INTERVALS)}")
    if period not in INTERVALS[interval]:
        raise ValueError(f"period for {interval} bars must be one of {', '.join(INTERVALS[interval])}")
    return md.history(symbol, period=period, interval=interval)


def _curve(dates, res, step: int = 1):
    eq = res["equity"]
    peak = np.maximum.accumulate(eq)
    return {"dates": dates[::step], "equity": md.to_float_list(eq[::step], 5), "drawdown": md.to_float_list((eq / peak - 1)[::step], 5)}


@router.get("")
async def catalog():
    return ok({
        "strategies": [{"id": k, "name": v[0], "description": v[1]} for k, v in rules.STRATEGIES.items()],
        "operands": rules.OPERANDS,
        "operators": rules.OPERATORS,
        "intervals": INTERVALS,
    }, cache_s=86400)


class CompareRequest(BaseModel):
    symbol: str = "SPY"
    period: str = "2y"
    interval: str = "1d"
    start: str | None = None
    end: str | None = None
    cost_bps: float = 5.0


def _compare(req: CompareRequest) -> dict:
    df = _load(req.symbol, req.period, req.interval)
    ppy = engine.periods_per_year(req.interval)
    out = []
    bh = rules.evaluate_window(df, np.ones(len(df)), req.start, req.end, 0.0)
    bh_m = engine.performance(bh["returns"], None, ppy)
    for sid, (name, desc, fn) in rules.STRATEGIES.items():
        r = rules.evaluate_window(df, fn(df), req.start, req.end, req.cost_bps)
        m = engine.performance(r["returns"], r["positions"], ppy)
        out.append({
            "id": sid, "name": name, "description": desc, "metrics": m, "trades": r["n_trades"],
            "trade_win_rate": r["win_rate"], "profit_factor": r["profit_factor"], "curve": _curve(r["dates"], r, max(1, len(r["dates"]) // 400)),
        })
    out.sort(key=lambda x: x["metrics"]["sharpe"] if x["metrics"]["sharpe"] is not None else -99, reverse=True)
    for i, o in enumerate(out):
        o["rank"] = i + 1
    return {
        "symbol": md.normalize_symbol(req.symbol), "period": req.period, "interval": req.interval, "cost_bps": req.cost_bps,
        "start": bh["dates"][0] if bh["dates"] else None, "end": bh["dates"][-1] if bh["dates"] else None,
        "strategies": out,
        "buy_hold": {"metrics": bh_m, "curve": _curve(bh["dates"], bh, max(1, len(bh["dates"]) // 400))},
    }


@router.post("/compare")
async def compare(req: CompareRequest):
    limit("strategies", 60)
    result = await run_in_threadpool(_compare, req)
    best = result["strategies"][0]
    prompt = (
        f"Rule-strategy backtest on {result['symbol']} ({req.interval} bars, {result['start']} to {result['end']}, {req.cost_bps} bps costs). "
        f"Ranking by Sharpe: " + "; ".join(f"{s['name']}: Sharpe {s['metrics']['sharpe']}, return {s['metrics']['total_return']}, max DD {s['metrics']['max_drawdown']}, trades {s['trades']}" for s in result["strategies"])
        + f". Buy and hold: Sharpe {result['buy_hold']['metrics']['sharpe']}, return {result['buy_hold']['metrics']['total_return']}. "
        "In 3-4 sentences explain why the leader worked on this symbol in this period, whether it beat buy-and-hold on a risk-adjusted basis, "
        "and one caution about over-reading a single backtest. No emojis, no advice to trade."
    )
    fallback = f"{best['name']} ranked first with a Sharpe of {best['metrics']['sharpe']} versus {result['buy_hold']['metrics']['sharpe']} for buy and hold."
    text, source = await llm.complete_or(fallback, prompt, effort="low", max_tokens=700)
    result["interpretation"] = {"text": text, "source": "ai" if source == "ai" else "data", "note": None if source in ("ai", "fallback") else source}
    return ok(result)


class Condition(BaseModel):
    left: dict
    op: str
    right: dict


class BacktestRequest(BaseModel):
    symbol: str = "SPY"
    period: str = "5y"
    interval: str = "1d"
    entry: list[Condition]
    exit: list[Condition] = Field(default_factory=list)
    stop_loss_pct: float = 0.0
    take_profit_pct: float = 0.0
    cost_bps: float = 5.0
    monte_carlo: bool = True
    mc_sims: int = 2000
    mc_horizon: int = 252


def _backtest(req: BacktestRequest) -> dict:
    df = _load(req.symbol, req.period, req.interval)
    ppy = engine.periods_per_year(req.interval)
    pos = rules.rule_positions(
        df, [c.model_dump() for c in req.entry], [c.model_dump() for c in req.exit],
        min(max(req.stop_loss_pct, 0), 50), min(max(req.take_profit_pct, 0), 500),
    )
    r = rules.evaluate_window(df, pos, None, None, min(max(req.cost_bps, 0), 50))
    bh = rules.evaluate_window(df, np.ones(len(df)), None, None, 0.0)
    m = engine.performance(r["returns"], r["positions"], ppy)
    trades = rules.trade_list(r["dates"], r)
    step = max(1, len(r["dates"]) // 600)
    out = {
        "symbol": md.normalize_symbol(req.symbol), "period": req.period, "interval": req.interval,
        "start": r["dates"][0], "end": r["dates"][-1],
        "metrics": {**m, "trades": r["n_trades"], "trade_win_rate": r["win_rate"], "profit_factor": r["profit_factor"],
                    "avg_trade": round(float(np.mean(r["trade_returns"])), 5) if r["trade_returns"] else None},
        "buy_hold": engine.performance(bh["returns"], None, ppy),
        "curve": _curve(r["dates"], r, step),
        "buy_hold_curve": _curve(bh["dates"], bh, step),
        "trades": trades[-200:],
    }
    if req.monte_carlo and r["n_trades"] > 0:
        try:
            out["monte_carlo"] = montecarlo.bootstrap(r["returns"], n_sims=req.mc_sims, horizon=req.mc_horizon)
        except ValueError as exc:
            out["monte_carlo"] = {"error": str(exc)}
    return out


@router.post("/backtest")
async def backtest(req: BacktestRequest):
    limit("strategies", 60)
    return ok(await run_in_threadpool(_backtest, req))
