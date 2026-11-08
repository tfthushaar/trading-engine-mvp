"""
Workspace tools: watchlist alerts, technical scanner, trade evaluator, portfolio lens, model-aware journal,
heatmap and the strategy arena across a watchlist. All stateless: the browser sends its own data.
"""
from __future__ import annotations

import json
import time

import numpy as np
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from backend import journal, portfolio
from backend.ai import llm
from backend.ai.insights import GROUNDING
from backend.dl.panel import UNIVERSE
from backend.http import limit, ok, ok_ai
from backend.market import data as md
from backend.market import overview, scanner
from backend.strategies import engine, evaluator, rules

router = APIRouter(prefix="/api", tags=["tools"])


def _src(source: str) -> dict:
    return {"source": "ai" if source == "ai" else "data", "note": None if source in ("ai", "fallback") else source}


# ---------------------------------------------------------------------------------------------
# Alerts and scanners
# ---------------------------------------------------------------------------------------------
NARRATION_SCHEMA = {
    "type": "object",
    "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {"id": {"type": "string"}, "narration": {"type": "string"}}, "required": ["id", "narration"], "additionalProperties": False}}},
    "required": ["items"], "additionalProperties": False,
}


# Alerts keep the same id for a symbol, type and day, so each one is narrated once however often clients poll
_narrations: dict[str, tuple[float, str]] = {}


@router.get("/alerts")
async def alerts(symbols: str = Query(...), narrate: bool = Query(True), options: bool = Query(True)):
    syms = [s for s in symbols.split(",") if s.strip()][:30]
    res = await run_in_threadpool(scanner.alerts, syms, options)
    for a in res["alerts"]:
        a["narration"] = a["detail"]
    res["source"] = "data"
    if narrate and res["alerts"]:
        now = time.time()
        top = res["alerts"][:8]
        for a in top:
            known = _narrations.get(a["id"])
            if known and known[0] > now:
                a["narration"] = known[1]
                res["source"] = "ai"
        todo = [a for a in top if not (_narrations.get(a["id"]) and _narrations[a["id"]][0] > now)]
        if todo:
            listing = "\n".join(f'{a["id"]}: {a["title"]}. {a["detail"]}' for a in todo)
            out, source = await llm.complete_or(None, f"Write one plain sentence per alert explaining what it means for someone watching the stock (no advice, no emojis).\n\n{listing}",
                                                system=GROUNDING, effort="low", max_tokens=900, schema=NARRATION_SCHEMA)
            if out:
                if len(_narrations) > 2000:
                    _narrations.clear()
                by_id = {i["id"]: i["narration"] for i in out.get("items", []) if isinstance(i, dict) and i.get("narration")}
                for a in todo:
                    if a["id"] in by_id:
                        a["narration"] = by_id[a["id"]]
                        _narrations[a["id"]] = (now + 86400, by_id[a["id"]])
            res.update(_src(source))
    return ok_ai(res, 60)


@router.get("/signals/technical/scan")
async def technical(symbols: str | None = Query(None)):
    syms = [s.strip().upper() for s in symbols.split(",") if s.strip()][:60] if symbols else list(UNIVERSE)
    return ok(await run_in_threadpool(scanner.technical_scan, syms), cache_s=120)


@router.get("/market/heatmap")
async def heatmap():
    universe = dict(UNIVERSE)
    for s in overview.MOVERS:
        universe.setdefault(s, (s, "Other"))
    return ok(await run_in_threadpool(scanner.heatmap, universe), cache_s=60)


# ---------------------------------------------------------------------------------------------
# Trade evaluator
# ---------------------------------------------------------------------------------------------
class EvalRequest(BaseModel):
    symbol: str
    entry: float
    stop: float
    target: float
    timeframe: str = "swing"


@router.post("/trade/evaluate")
async def evaluate(req: EvalRequest):
    limit("tools", 60)
    res = await run_in_threadpool(evaluator.evaluate, req.symbol, req.entry, req.stop, req.target, req.timeframe)
    prompt = (
        f"Assess this {res['direction']} trade plan as a trading coach in 3-4 sentences: setup quality, key strength, key risk, one improvement.\n\n"
        f"{json.dumps({k: res[k] for k in ('symbol', 'score', 'grade', 'components', 'risk_reward', 'context', 'signals', 'warnings', 'neural')}, default=str)}"
    )
    fallback = f"Grade {res['grade']} ({res['score']}/100). " + (res["warnings"][0] if res["warnings"] else (res["signals"][0] if res["signals"] else ""))
    text, source = await llm.complete_or(fallback, prompt, system=GROUNDING, effort="low", max_tokens=600)
    res["assessment"] = {"text": text, **_src(source)}
    return ok(res)


# ---------------------------------------------------------------------------------------------
# Portfolio lens
# ---------------------------------------------------------------------------------------------
class PortfolioRequest(BaseModel):
    positions: list[dict] = Field(default_factory=list)
    narrate: bool = True


@router.post("/portfolio/analyze")
async def analyze_portfolio(req: PortfolioRequest):
    limit("tools", 60)
    res = await run_in_threadpool(portfolio.analyze, req.positions)
    if req.narrate:
        compact = {
            "positions": [{k: p.get(k) for k in ("symbol", "weight", "pnl_pct", "sector", "neural")} for p in res["positions"] if "value" in p],
            "sectors": res["sectors"], "risk": res["risk"], "concentration": res["concentration"],
            "avg_correlation": (res["correlation"] or {}).get("avg_pairwise"), "health": res["health"], "neural_summary": res["neural_summary"],
        }
        prompt = (
            "Write a portfolio health assessment in 4 sentences: concentration, diversification and correlation, risk level, and what the neural "
            f"signals on the holdings suggest. Close with one construction suggestion (not a trade).\n\n{json.dumps(compact, default=str)}"
        )
        fallback = " ".join(res["health"]["notes"]) or "The portfolio is reasonably diversified across the positions entered."
        text, source = await llm.complete_or(fallback, prompt, system=GROUNDING, effort="low", max_tokens=700)
        res["assessment"] = {"text": text, **_src(source)}
    return ok(res)


# ---------------------------------------------------------------------------------------------
# Model-aware trade journal
# ---------------------------------------------------------------------------------------------
class JournalRequest(BaseModel):
    entries: list[dict] = Field(default_factory=list)
    coach: bool = True


@router.post("/journal/analyze")
async def analyze_journal(req: JournalRequest):
    limit("tools", 60)
    res = await run_in_threadpool(journal.analyze, req.entries)
    if req.coach and res.get("score") is not None:
        prompt = (
            "You are a trading performance coach. In 4-5 sentences: acknowledge what is working, name the single most important behaviour to fix, "
            "comment on whether trades taken with or against the neural model did better, and give one concrete habit for next month.\n\n"
            f"{json.dumps({k: res[k] for k in ('score', 'grade', 'rule_adherence', 'stats', 'patterns', 'by_emotion', 'vs_model')}, default=str)}"
        )
        fallback = f"Discipline score {res['score']}/100. " + (res["patterns"][0]["description"] if res["patterns"] else "No problematic patterns detected.")
        text, source = await llm.complete_or(fallback, prompt, system=GROUNDING, effort="low", max_tokens=700)
        res["coaching"] = {"text": text, **_src(source)}
    return ok(res)


class ReviewRequest(BaseModel):
    entry: dict


@router.post("/journal/review")
async def review_trade(req: ReviewRequest):
    limit("tools", 60)
    e = req.entry
    prompt = (
        "Review this completed trade in 3 sentences: was the process sound regardless of outcome, the key lesson, and what to repeat or change. "
        f"Mention whether it followed or opposed the neural model signal recorded at entry.\n\n{json.dumps(e, default=str)[:3000]}"
    )
    pnl = journal._pnl_pct(e)
    fallback = f"Closed {e.get('direction', 'long')} trade in {e.get('symbol', '')} at {'' if pnl is None else f'{pnl:+.2f}%'}. Compare the exit with your plan and note what you would repeat."
    text, source = await llm.complete_or(fallback, prompt, system=GROUNDING, effort="low", max_tokens=500)
    return ok({"review": text, **_src(source)})


# ---------------------------------------------------------------------------------------------
# Strategy arena across several symbols (rule agents compete per symbol)
# ---------------------------------------------------------------------------------------------
class CompetitionRequest(BaseModel):
    symbols: list[str]
    period: str = "2y"
    interval: str = "1d"
    cost_bps: float = 5.0
    slippage_bps: float = 2.0


def _competition(req: CompetitionRequest) -> dict:
    syms = md.valid_symbols(req.symbols)[:20]
    if not syms:
        raise ValueError("enter at least one valid symbol")
    data = md.histories(syms, period=req.period, interval=req.interval)
    ppy = engine.periods_per_year(req.interval)
    cost = min(max(req.cost_bps, 0), 50) + min(max(req.slippage_bps, 0), 50)
    per, wins = [], {k: 0 for k in rules.STRATEGIES}
    for s in syms:
        df = data.get(s)
        if df is None or len(df) < 120:
            continue
        bh = rules.evaluate_window(df, np.ones(len(df)), None, None, 0.0)
        ranking = []
        for sid, (name, _desc, fn) in rules.STRATEGIES.items():
            r = rules.evaluate_window(df, fn(df), None, None, cost)
            m = engine.performance(r["returns"], r["positions"], ppy)
            ranking.append({"id": sid, "name": name, "sharpe": m["sharpe"], "total_return": m["total_return"], "max_drawdown": m["max_drawdown"], "trades": r["n_trades"]})
        ranking.sort(key=lambda x: x["sharpe"] if x["sharpe"] is not None else -99, reverse=True)
        wins[ranking[0]["id"]] += 1
        per.append({"symbol": s, "winner": ranking[0]["name"], "ranking": ranking, "buy_hold": engine.performance(bh["returns"], None, ppy)})
    best = max(wins, key=wins.get) if per else None
    return {"symbols": syms, "period": req.period, "interval": req.interval, "cost_bps": cost, "results": per,
            "win_counts": {rules.STRATEGIES[k][0]: v for k, v in wins.items()}, "overall_best": rules.STRATEGIES[best][0] if best else None}


@router.post("/strategies/competition")
async def competition(req: CompetitionRequest):
    limit("strategies", 30)
    res = await run_in_threadpool(_competition, req)
    if res["results"]:
        summary = [{"symbol": r["symbol"], "winner": r["winner"], "winner_sharpe": r["ranking"][0]["sharpe"], "buy_hold_sharpe": r["buy_hold"]["sharpe"]} for r in res["results"]]
        prompt = (
            f"Five rule-based strategy agents competed on {len(summary)} symbols ({req.interval} bars, {req.period}, {res['cost_bps']} bps costs incl. slippage). "
            f"Win counts: {res['win_counts']}. Per symbol: {json.dumps(summary)}. In 3-4 sentences, as a quant coach: which style dominated and why that fits these symbols "
            "in this period, how often any rule beat buy-and-hold on Sharpe, and a caution about selection bias."
        )
        fallback = f"{res['overall_best']} won on the most symbols."
        text, source = await llm.complete_or(fallback, prompt, system=GROUNDING, effort="low", max_tokens=700)
        res["interpretation"] = {"text": text, **_src(source)}
    return ok(res)
