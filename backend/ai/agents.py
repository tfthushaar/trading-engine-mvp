"""
Analyst: a small multi-agent system.

A deterministic router (keywords + symbol detection, no LLM call) picks one specialist. The specialist
gathers grounded data (market snapshot, technicals, neural-ensemble readings, rule-strategy backtests,
concept notes), then a single LLM call writes the answer. One message = at most one LLM call.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from backend.ai import education, llm
from backend.ai.insights import DISCLAIMER, GROUNDING
from backend.dl import global_model
from backend.dl.panel import UNIVERSE
from backend.market import data as md
from backend.market import indicators as ind
from backend.market import overview
from backend.strategies import rules

AGENTS = {
    "news": "News analyst: what the latest headlines mean for a symbol or the market.",
    "market": "Market analyst: what is moving and why, sectors, breadth, regime.",
    "trade_reviewer": "Trade reviewer: grades an entry, stop and target plan, including the neural model's view.",
    "portfolio": "Portfolio analyst: diversification, correlation and neural signals across your holdings.",
    "ticker": "Symbol analyst: price action, technicals, news and the model view for specific symbols.",
    "model": "Model analyst: what the neural ensemble predicts, how reliable it is, how it works.",
    "strategy": "Strategy analyst: rule strategies, backtests, what has worked on a symbol.",
    "risk": "Risk coach: position sizing, stops, volatility, drawdowns.",
    "education": "Educator: explains trading and deep-learning concepts.",
}

NAMES = {
    "apple": "AAPL", "microsoft": "MSFT", "nvidia": "NVDA", "google": "GOOGL", "alphabet": "GOOGL", "amazon": "AMZN",
    "meta": "META", "facebook": "META", "tesla": "TSLA", "netflix": "NFLX", "broadcom": "AVGO", "intel": "INTC",
    "jpmorgan": "JPM", "visa": "V", "mastercard": "MA", "exxon": "XOM", "chevron": "CVX", "walmart": "WMT",
    "costco": "COST", "boeing": "BA", "disney": "DIS", "pfizer": "PFE", "lilly": "LLY", "bitcoin": "BTC-USD",
    "s&p": "SPY", "s&p 500": "SPY", "nasdaq": "QQQ", "gold": "GC=F", "oil": "CL=F",
}
NOT_SYMBOLS = {
    "I", "A", "AI", "RSI", "MACD", "EMA", "SMA", "ATR", "ETF", "ETFS", "CEO", "CFO", "USA", "US", "GDP", "CPI", "FED", "FOMC", "EPS",
    "LSTM", "GRU", "TCN", "MLP", "CNN", "IPO", "PE", "OK", "THE", "AND", "OR", "IS", "IT", "VS", "YOY", "QOQ", "ATH", "DCA", "MC",
    "SEC", "API", "UI", "PM", "AM", "EST", "UTC", "NYSE", "BB", "VWAP", "TA", "FA", "Q1", "Q2", "Q3", "Q4", "HOW", "WHAT", "WHY",
}
KNOWN = set(UNIVERSE) | set(overview.MOVERS) | set(overview.SECTORS)


def detect_symbols(text: str) -> list[str]:
    found: list[str] = []
    for m in re.findall(r"\$([A-Za-z][A-Za-z.\-]{0,9})", text):
        found.append(m.upper())
    for tok in re.findall(r"\b[A-Z]{1,5}(?:[.\-][A-Z]{1,2})?\b", text):
        if tok in NOT_SYMBOLS:
            continue
        if tok in KNOWN or len(tok) >= 2:
            found.append(tok)
    low = text.lower()
    for name, sym in NAMES.items():
        if re.search(rf"\b{re.escape(name)}\b", low):
            found.append(sym)
    out = []
    for s in found:
        if s not in out:
            out.append(s)
    return out[:3]


PRICE = r"\$?\d+(?:\.\d+)?"


def parse_trade(text: str) -> dict | None:
    low = text.lower()

    def get(words):
        return re.search(rf"(?:{words})\D{{0,12}}({PRICE})", low)

    e, s, t = get("entry|enter|buy at|long at|short at|in at"), get("stop loss|stop|sl"), get("target|take profit|tp")
    if e and s and t:
        return {k: float(m.group(1).replace("$", "")) for k, m in (("entry", e), ("stop", s), ("target", t))}
    return None


def route(text: str, has_portfolio: bool = False) -> tuple[str, list[str]]:
    low = text.lower()
    syms = detect_symbols(text)
    if parse_trade(text) and syms:
        return "trade_reviewer", syms
    if has_portfolio and re.search(r"\b(my portfolio|my holdings|my positions|diversif|correlat|rebalanc|allocation)", low):
        return "portfolio", syms
    if re.search(r"\b(news|headline|announce|earnings|what happened|why is \w+ (up|down))", low):
        return "news", syms
    if re.search(r"\b(neural|model|lstm|gru|tcn|transformer|ensemble|attention|probabilit|forecast|predict|confidence|calibrat|deep learning|training|overfit)", low):
        agent = "model"
    elif re.search(r"\b(what is|what's a|what are|explain|define|meaning of|how does|how do .* work|teach me|difference between)", low) and not syms:
        agent = "education"
    elif re.search(r"\b(strateg|backtest|crossover|mean reversion|breakout|momentum strategy|rule)", low):
        agent = "strategy"
    elif re.search(r"\b(risk|position size|sizing|stop loss|stop-loss|drawdown|hedge|diversif|how much should i|leverage)", low):
        agent = "risk"
    elif syms:
        agent = "ticker"
    else:
        agent = "market"
    return agent, syms


def _ticker_ctx(sym: str) -> dict:
    out: dict = {"symbol": sym}
    try:
        df = md.history(sym, period="2y")
        out["technicals"] = ind.snapshot(df)
    except Exception as exc:
        out["error"] = str(exc)
        return out
    try:
        d = global_model.symbol_detail(sym, lookback=20)
        out["neural_ensemble"] = {k: d[k] for k in ("horizon_days", "prob_up", "signal", "agreement", "uncertainty", "calibrated", "members")}
    except Exception:
        pass
    out["headlines"] = [n["title"] for n in md.news(sym, limit=5)]
    return out


def _strategy_ctx(sym: str) -> dict:
    df = md.history(sym, period="2y")
    res = []
    for name, desc, fn in rules.STRATEGIES.values():
        r = rules.evaluate_window(df, fn(df), None, None, 5.0)
        res.append({"strategy": name, "rule": desc, **{k: r["metrics"][k] for k in ("total_return", "sharpe", "max_drawdown")}, "trades": r["n_trades"]})
    bh = rules.evaluate_window(df, rules.np.ones(len(df)), None, None, 0.0)
    return {"symbol": sym, "period": "2y daily", "strategies": sorted(res, key=lambda x: x["sharpe"] or -9, reverse=True), "buy_and_hold": bh["metrics"]}


def build_context(agent: str, syms: list[str], text: str, portfolio_positions: list[dict] | None = None) -> dict:
    ctx: dict = {"agent": agent, "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%d")}
    if agent == "news":
        targets = syms or ["SPY", "QQQ"]
        ctx["headlines"] = {
            s: [{"title": n["title"], "source": n["source"], "published_at": n["published_at"], "summary": n.get("summary")} for n in md.news(s, limit=8)]
            for s in targets[:3]
        }
        if syms:
            ctx["symbols"] = [_ticker_ctx(s) for s in syms[:2]]
    if agent == "trade_reviewer" and syms:
        from backend.strategies import evaluator

        plan = parse_trade(text)
        try:
            ctx["evaluation"] = evaluator.evaluate(syms[0], plan["entry"], plan["stop"], plan["target"])
        except Exception as exc:
            ctx["evaluation_error"] = str(exc)
    if agent == "portfolio" and portfolio_positions:
        from backend import portfolio as pf

        try:
            a = pf.analyze(portfolio_positions)
            ctx["portfolio"] = {
                "positions": [{k: p.get(k) for k in ("symbol", "weight", "pnl_pct", "sector", "neural")} for p in a["positions"] if "value" in p],
                "sectors": a["sectors"], "risk": a["risk"], "health": a["health"], "avg_correlation": (a["correlation"] or {}).get("avg_pairwise"),
            }
        except Exception as exc:
            ctx["portfolio_error"] = str(exc)
    if agent in ("market",) or (agent == "model" and not syms):
        snap = overview.snapshot()
        ctx["market"] = {
            "macro": [{k: m[k] for k in ("label", "price", "change_pct")} for m in snap["macro"]],
            "sectors": [{k: s[k] for k in ("label", "change_pct")} for s in snap["sectors"]],
            "gainers": [g["symbol"] + f" {g['change_pct']:+.2f}%" for g in snap["gainers"][:5]],
            "losers": [g["symbol"] + f" {g['change_pct']:+.2f}%" for g in snap["losers"][:5]],
        }
        ctx["regime"] = overview.regime()
        try:
            sc = global_model.scan(mc_samples=0)
            ctx["neural_breadth"] = sc["breadth"]
            ctx["most_bullish"] = [f"{r['symbol']} {r['prob_up']:.2f}" for r in sc["rows"][:5]]
            ctx["most_bearish"] = [f"{r['symbol']} {r['prob_up']:.2f}" for r in sc["rows"][-5:]]
        except Exception:
            pass
    if agent in ("ticker", "model", "risk") and syms:
        ctx["symbols"] = [_ticker_ctx(s) for s in syms]
    if agent == "model":
        try:
            card = global_model.card()
            ctx["model_card"] = {
                "members": [{"name": m["name"], "params": m["n_params"], "test_auc": m["test"]["auc"], "test_accuracy": m["test"]["accuracy"]} for m in card["members"]],
                "ensemble_test": {k: card["ensemble"]["test"][k] for k in ("accuracy", "auc", "log_loss", "brier")},
                "baseline_log_loss": card["ensemble"]["baseline_train_base_rate"]["log_loss"],
                "test_period": card["splits"]["test"], "horizon_days": card["horizon"], "window": card["window"],
                "calibration": card["calibration"], "backtest": card["backtest"]["metrics"],
            }
        except Exception:
            ctx["model_card"] = "unavailable"
    if agent == "strategy" and syms:
        try:
            ctx["backtests"] = [_strategy_ctx(s) for s in syms[:2]]
        except Exception as exc:
            ctx["backtests_error"] = str(exc)
    if agent in ("education", "model", "strategy", "risk"):
        low = text.lower()
        hits = [c for k, c in education.CONCEPTS.items() if k.replace("_", " ") in low or c["title"].lower().split(" ")[0] in low]
        ctx["concepts"] = [{"title": c["title"], "summary": c["summary"], "in_product": c["in_app"]} for c in hits[:3]]
    return ctx


SYSTEM = (
    "You are the analyst inside Trading Engine, a public market-intelligence product whose forecasts come from "
    "neural networks (an LSTM, GRU, temporal CNN and Transformer ensemble predicting 5-day direction). "
    + GROUNDING
    + " Answer in concise markdown (short paragraphs or bullets, at most about 250 words). When the neural ensemble is "
    "relevant, state its probability, member agreement and calibrated hit rate, and remind the reader that edges are small."
)


def _fallback_answer(agent: str, ctx: dict) -> str:
    lines = [f"AI narration is not available right now, so here is the data the {agent} specialist gathered."]
    for s in ctx.get("symbols", []):
        t = s.get("technicals") or {}
        n = s.get("neural_ensemble")
        lines.append(f"\n**{s['symbol']}** price {t.get('price', 0):.2f}, trend {t.get('trend')}, RSI {t.get('rsi_14') or 0:.0f}.")
        if n:
            lines.append(f"Neural ensemble P(up, {n['horizon_days']}d) = {n['prob_up']:.2f}, agreement {int(n['agreement'] * 100)}%.")
    if "regime" in ctx:
        lines.append(f"\nRegime: {ctx['regime'].get('description')}")
    if "neural_breadth" in ctx:
        b = ctx["neural_breadth"]
        lines.append(f"Neural breadth: {b['bullish']} bullish, {b['neutral']} neutral, {b['bearish']} bearish.")
    for c in ctx.get("concepts", []):
        lines.append(f"\n**{c['title']}.** {c['summary']}")
    for b in ctx.get("backtests", []):
        top = b["strategies"][0]
        lines.append(f"\nBest rule strategy on {b['symbol']} ({b['period']}): {top['strategy']}, Sharpe {top['sharpe']}.")
    return "\n".join(lines)


async def chat(message: str, history: list[dict] | None = None, portfolio_positions: list[dict] | None = None) -> dict:
    message = message.strip()[:2000]
    if not message:
        raise ValueError("empty message")
    agent, syms = route(message, has_portfolio=bool(portfolio_positions))
    ctx = build_context(agent, syms, message, portfolio_positions)
    convo = []
    for h in (history or [])[-8:]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            convo.append({"role": h["role"], "content": str(h["content"])[:1500]})
    if convo and convo[0]["role"] == "assistant":
        convo = convo[1:]
    user = f"Data gathered by the {agent} specialist ({AGENTS[agent]}):\n{json.dumps(ctx, default=str)[:9000]}\n\nQuestion: {message}"
    msgs = convo + [{"role": "user", "content": user}]
    text, source = await llm.complete_or(_fallback_answer(agent, ctx), msgs, system=SYSTEM, effort="low", max_tokens=1500)
    return {
        "agent": agent,
        "agent_description": AGENTS[agent],
        "symbols": syms,
        "answer": text,
        "source": "ai" if source == "ai" else "data",
        "note": None if source in ("ai", "fallback") else source,
        "disclaimer": DISCLAIMER,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
