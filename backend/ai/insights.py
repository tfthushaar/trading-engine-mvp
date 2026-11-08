"""
Plain-language interpretation of the data and the neural models: market briefing, ticker brief, news read.

Every function returns usable output without an API key (deterministic text built from the numbers);
with a key, Claude writes the narrative from the same grounded inputs.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from backend.ai import llm
from backend.dl import global_model
from backend.market import data as md
from backend.market import indicators as ind
from backend.market import overview

DISCLAIMER = "Educational analysis from statistical models and public data. Not financial advice."
_cache: dict[str, tuple[float, dict]] = {}

GROUNDING = (
    "Use only the data provided. The FACTS block is authoritative for prices, percentage moves and dates; headlines may describe "
    "earlier sessions, so never take today's moves or the day of the week from a headline. "
    "Do not invent news, events, earnings dates or price levels that are not in the data. "
    "If something is unknown, say so briefly. Write plainly for a general audience: short sentences, no hype, no emojis, "
    "no exclamation marks. Never tell the reader to buy or sell; describe what the evidence suggests and what would change it."
)


def _cached(key: str, ttl: float):
    hit = _cache.get(key)
    return hit[1] if hit and hit[0] > time.time() else None


def _store(key: str, ttl: float, value: dict) -> dict:
    if value.get("source") == "ai":
        _cache[key] = (time.time() + ttl, value)
    return value


def _pct(x, digits=2):
    return "n/a" if x is None else f"{x:+.{digits}f}%"


def _session_label(date_str: str | None) -> str:
    if not date_str:
        return "unknown"
    from datetime import date

    d = date.fromisoformat(date_str[:10])
    return f"{d.strftime('%A')} {d.isoformat()}"


def _safe_scan() -> dict | None:
    try:
        return global_model.scan(mc_samples=0)
    except Exception:
        return None


# --------------------------------------------------------------------------------------------
# Market briefing
# --------------------------------------------------------------------------------------------
BRIEFING_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "summary": {"type": "string"},
        "drivers": {"type": "array", "items": {"type": "string"}},
        "model_view": {"type": "string"},
        "watch": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["headline", "summary", "drivers", "model_view", "watch", "risks"],
    "additionalProperties": False,
}


def _fallback_briefing(snap: dict, reg: dict, scan: dict | None) -> dict:
    by = {m["symbol"]: m for m in snap["macro"]}
    spy, vix = by.get("SPY"), by.get("^VIX")
    lead, lag = (snap["sectors"][0], snap["sectors"][-1]) if snap["sectors"] else (None, None)
    b = snap["breadth"]
    tone = "higher" if spy and (spy["change_pct"] or 0) > 0.2 else "lower" if spy and (spy["change_pct"] or 0) < -0.2 else "little changed"
    headline = f"US stocks {tone}; {lead['label'] if lead else 'sectors'} lead"
    summary = (
        f"The S&P 500 is {_pct(spy['change_pct'] if spy else None)} on the day"
        + (f" with the VIX at {vix['price']:.1f}" if vix else "")
        + f". {b['advancing']} of {b['universe']} large caps tracked are up. Regime: {reg.get('description', 'n/a')}"
    )
    drivers = []
    if lead and lag:
        drivers.append(f"Sector spread: {lead['label']} {_pct(lead['change_pct'])} vs {lag['label']} {_pct(lag['change_pct'])}.")
    if snap["gainers"]:
        g = snap["gainers"][0]
        drivers.append(f"Biggest gainer tracked: {g['symbol']} {_pct(g['change_pct'])}.")
    if snap["losers"]:
        lo = snap["losers"][0]
        drivers.append(f"Biggest decliner tracked: {lo['symbol']} {_pct(lo['change_pct'])}.")
    model_view = "Neural ensemble unavailable."
    if scan:
        br = scan["breadth"]
        model_view = (
            f"The neural ensemble scores {br['bullish']} symbols bullish, {br['neutral']} neutral and {br['bearish']} bearish "
            f"for the next {scan['horizon_days']} trading days (average P(up) {br['mean_prob_up']:.2f})."
        )
    return {
        "headline": headline, "summary": summary, "drivers": drivers, "model_view": model_view,
        "watch": ["Whether the leading sector holds its gains into the close.", "VIX direction as a gauge of risk appetite."],
        "risks": ["Model probabilities sit close to 50%; treat them as tilts, not forecasts."],
    }


async def market_briefing() -> dict:
    hit = _cached("briefing", 1800)
    if hit:
        return hit
    snap = overview.snapshot()
    reg = overview.regime()
    scan = _safe_scan()
    headlines = md.news("SPY", limit=8) + md.news("QQQ", limit=4)
    fallback = _fallback_briefing(snap, reg, scan)
    by = {m["symbol"]: m for m in snap["macro"]}
    session = (by.get("SPY") or {}).get("as_of") or snap["as_of"]
    facts = [f"Latest US equity session: {_session_label(session)}. Today is {_session_label(datetime.now(timezone.utc).date().isoformat())}."]
    for sym in ("SPY", "QQQ", "IWM", "DIA", "^VIX", "^TNX"):
        m = by.get(sym)
        if m:
            facts.append(f"{m['label']} ({sym}): {m['price']:.2f}, {m['change_pct']:+.2f}% on that session")
    if snap["sectors"]:
        facts.append(f"Best sector: {snap['sectors'][0]['label']} {snap['sectors'][0]['change_pct']:+.2f}%; worst: {snap['sectors'][-1]['label']} {snap['sectors'][-1]['change_pct']:+.2f}%")
    facts.append(f"Breadth among {snap['breadth']['universe']} large caps: {snap['breadth']['advancing']} up, {snap['breadth']['declining']} down")
    context = {
        "as_of": session,
        "macro": [{k: m[k] for k in ("label", "price", "change_pct")} for m in snap["macro"]],
        "sectors": [{k: s[k] for k in ("label", "change_pct")} for s in snap["sectors"]],
        "gainers": [{k: g[k] for k in ("symbol", "change_pct", "volume_ratio")} for g in snap["gainers"]],
        "losers": [{k: g[k] for k in ("symbol", "change_pct", "volume_ratio")} for g in snap["losers"]],
        "breadth": snap["breadth"],
        "regime": reg,
        "neural_ensemble": None if not scan else {
            "horizon_days": scan["horizon_days"], "breadth": scan["breadth"],
            "most_bullish": [{k: r[k] for k in ("symbol", "prob_up", "agreement")} for r in scan["rows"][:5]],
            "most_bearish": [{k: r[k] for k in ("symbol", "prob_up", "agreement")} for r in scan["rows"][-5:]],
        },
        "headlines": [{"title": h["title"], "source": h["source"], "published_at": h["published_at"]} for h in headlines[:12]],
    }
    prompt = (
        "Write today's market briefing for a public market-intelligence site from this JSON data.\n\n"
        f"{json.dumps(context, default=str)}\n\n"
        "headline: under 12 words. summary: 2-3 sentences on what is happening. drivers: 3-4 bullets tying moves to the data "
        "or headlines. model_view: 1-2 sentences on what the neural ensemble shows and how much weight it deserves. "
        "watch: 3 concrete things to watch next. risks: 2-3 risks to the current picture."
    )
    result, source = await llm.complete_or(fallback, prompt, system=GROUNDING, effort="medium", schema=BRIEFING_SCHEMA, max_tokens=2500)
    out = {
        **result, "source": "ai" if source == "ai" else "data", "note": None if source in ("ai", "fallback") else source,
        "regime": reg, "as_of": session, "headlines": headlines[:8], "disclaimer": DISCLAIMER,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return _store("briefing", 1800, out)


# --------------------------------------------------------------------------------------------
# Ticker brief
# --------------------------------------------------------------------------------------------
TICKER_SCHEMA = {
    "type": "object",
    "properties": {
        "stance": {"type": "string", "enum": ["bullish", "bearish", "neutral", "mixed"]},
        "summary": {"type": "string"},
        "happening": {"type": "array", "items": {"type": "string"}},
        "model": {"type": "string"},
        "consider": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["stance", "summary", "happening", "model", "consider", "risks"],
    "additionalProperties": False,
}


def _fallback_ticker(sym: str, tech: dict, det: dict | None) -> dict:
    trend = {"up": "an uptrend (above its 20, 50 and 200-day averages)", "down": "a downtrend (below its 20, 50 and 200-day averages)"}.get(tech["trend"], "a mixed trend")
    rsi = tech.get("rsi_14")
    happening = [f"Price is in {trend}."]
    if rsi is not None:
        zone = "overbought territory" if rsi >= 70 else "oversold territory" if rsi <= 30 else "a neutral range"
        happening.append(f"RSI(14) is {rsi:.0f}, {zone}.")
    if tech.get("return_1m") is not None:
        happening.append(f"1-month return {tech['return_1m'] * 100:+.1f}%, 3-month {((tech.get('return_3m') or 0) * 100):+.1f}%.")
    model = "Neural ensemble unavailable for this symbol."
    stance = "neutral"
    if det:
        stance = det["signal"]
        cal = det.get("calibrated")
        model = (
            f"The ensemble puts P(up over {det['horizon_days']} days) at {det['prob_up']:.2f} with {int(det['agreement'] * 100)}% of members agreeing"
            + (f"; historically, readings in this band rose {cal['historical_up_frequency'] * 100:.0f}% of the time" if cal else "")
            + "."
        )
    return {
        "stance": stance, "summary": f"{sym}: {happening[0]}", "happening": happening, "model": model,
        "consider": ["Position size relative to recent volatility.", "Where a stop would sit relative to the 50-day average."],
        "risks": ["Model edges on daily equity data are small and unstable over time."],
    }


async def ticker_brief(symbol: str) -> dict:
    sym = md.normalize_symbol(symbol)
    key = f"ticker:{sym}"
    hit = _cached(key, 1800)
    if hit:
        return hit
    df = md.history(sym, period="2y")
    tech = ind.snapshot(df)
    try:
        det = global_model.symbol_detail(sym, lookback=60)
    except Exception:
        det = None
    news = md.news(sym, limit=8)
    prof = md.profile(sym)
    fallback = _fallback_ticker(sym, tech, det)
    last_date = df.index[-1].strftime("%Y-%m-%d")
    day_move = (float(df["Close"].iloc[-1]) / float(df["Close"].iloc[-2]) - 1) * 100 if len(df) > 1 else 0.0
    facts = [
        f"Latest session: {_session_label(last_date)}",
        f"{sym} close {tech['price']:.2f}, {day_move:+.2f}% on that session",
        f"1-month {((tech.get('return_1m') or 0) * 100):+.1f}%, 3-month {((tech.get('return_3m') or 0) * 100):+.1f}%, 1-year {((tech.get('return_1y') or 0) * 100):+.1f}%",
        f"RSI(14) {tech.get('rsi_14') or 0:.1f}; trend vs 20/50/200-day averages: {tech['trend']}",
    ]
    if det:
        facts.append(f"Neural ensemble P(up over {det['horizon_days']} sessions) = {det['prob_up']:.3f}, signal {det['signal']}, member agreement {det['agreement']:.0%}")
    context = {
        "symbol": sym, "profile": {k: prof.get(k) for k in ("name", "sector", "industry", "market_cap", "pe", "beta")},
        "technicals": tech,
        "neural_ensemble": None if not det else {k: det[k] for k in ("horizon_days", "prob_up", "signal", "agreement", "uncertainty", "members", "calibrated")},
        "headlines": [{"title": n["title"], "source": n["source"], "published_at": n["published_at"]} for n in news],
    }
    prompt = (
        f"Explain what is happening with {sym} and what the neural models see, from this JSON data.\n\n{json.dumps(context, default=str)}\n\n"
        "stance: overall read of the evidence. summary: 2 sentences. happening: 3-4 bullets (price action, technicals, news). "
        "model: 1-2 sentences interpreting the ensemble probability, member agreement, uncertainty and calibration honestly. "
        "consider: 3 practical things a careful person would weigh before acting. risks: 2-3 bullets."
    )
    result, source = await llm.complete_or(fallback, prompt, system=GROUNDING, effort="low", schema=TICKER_SCHEMA)
    out = {
        "symbol": sym, **result, "source": "ai" if source == "ai" else "data", "note": None if source in ("ai", "fallback") else source,
        "technicals": tech, "disclaimer": DISCLAIMER, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return _store(key, 1800, out)


# --------------------------------------------------------------------------------------------
# News read
# --------------------------------------------------------------------------------------------
NEWS_SCHEMA = {
    "type": "object",
    "properties": {
        "tone": {"type": "string", "enum": ["positive", "negative", "neutral", "mixed"]},
        "impact": {"type": "string", "enum": ["low", "medium", "high"]},
        "summary": {"type": "string"},
        "themes": {"type": "array", "items": {"type": "string"}},
        "affected_sectors": {"type": "array", "items": {"type": "string"}},
        "items": {"type": "array", "items": {"type": "object", "properties": {"i": {"type": "integer"}, "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]}}, "required": ["i", "sentiment"], "additionalProperties": False}},
    },
    "required": ["tone", "impact", "summary", "themes", "affected_sectors", "items"],
    "additionalProperties": False,
}
_POS = {"beat", "beats", "surge", "surges", "record", "upgrade", "upgrades", "rally", "gain", "gains", "jump", "jumps", "growth", "raise", "raises", "strong", "soar", "soars", "rise", "rises", "higher", "profit"}
_NEG = {"miss", "misses", "plunge", "plunges", "downgrade", "downgrades", "cut", "cuts", "fall", "falls", "drop", "drops", "lawsuit", "probe", "weak", "loss", "losses", "slump", "decline", "declines", "lower", "warns", "layoffs"}


def _lexicon(title: str) -> str:
    w = {t.strip(".,:;!?'\"()").lower() for t in title.split()}
    p, n = len(w & _POS), len(w & _NEG)
    return "positive" if p > n else "negative" if n > p else "neutral"


async def news_read(symbol: str) -> dict:
    sym = md.normalize_symbol(symbol)
    key = f"news:{sym}"
    hit = _cached(key, 1800)
    if hit:
        return hit
    items = md.news(sym, limit=10)
    for it in items:
        it["sentiment"] = _lexicon(it["title"])
    counts = {s: sum(1 for it in items if it["sentiment"] == s) for s in ("positive", "negative", "neutral")}
    tone = "neutral" if not items else max(counts, key=counts.get) if max(counts.values()) > len(items) / 2 else "mixed"
    fallback = {"tone": tone, "impact": "low", "summary": f"{len(items)} recent headlines; keyword sentiment is {tone}." if items else "No recent headlines.", "themes": [], "affected_sectors": [], "items": []}
    if items:
        listing = "\n".join(f"[{i}] {it['title']} ({it['source']}, {it['published_at']}) {it.get('summary') or ''}" for i, it in enumerate(items))
        prompt = (
            f"Classify these recent headlines about {sym}.\n\n{listing}\n\n"
            "tone and impact for the stock overall; summary: 2 sentences on what the news flow is about and why it may matter; "
            "themes: up to 4 short labels; affected_sectors: sectors these stories could move (may be empty); items: the sentiment of each headline by index i."
        )
        result, source = await llm.complete_or(fallback, prompt, system=GROUNDING, effort="low", schema=NEWS_SCHEMA)
    else:
        result, source = fallback, "fallback"
    for row in result.get("items", []):
        if isinstance(row, dict) and 0 <= row.get("i", -1) < len(items):
            items[row["i"]]["sentiment"] = row["sentiment"]
    out = {
        "symbol": sym, "tone": result["tone"], "impact": result["impact"], "summary": result["summary"], "themes": result.get("themes", []), "affected_sectors": result.get("affected_sectors", []),
        "articles": items, "source": "ai" if source == "ai" else "data", "note": None if source in ("ai", "fallback") else source,
        "disclaimer": DISCLAIMER,
    }
    return _store(key, 1800, out)
