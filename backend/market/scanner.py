"""
Watchlist intelligence: anomaly alerts and the technical (RSI + EMA) signal scanner.

Stateless: the client sends the symbols it watches and polls; notifications are kept in the browser.
"""
from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from backend.market import data as md
from backend.market import indicators as ind

SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


def _technical_row(sym: str, df: pd.DataFrame) -> dict | None:
    if df is None or len(df) < 60:
        return None
    c, v = df["Close"], df["Volume"]
    r = float(ind.rsi(c).iloc[-1])
    e20, e50 = float(ind.ema(c, 20).iloc[-1]), float(ind.ema(c, 50).iloc[-1])
    last = float(c.iloc[-1])
    vol_ratio = float(v.iloc[-1] / v.tail(20).mean()) if v.tail(20).mean() else 1.0
    score, reasons = 0, []
    if r < 35:
        score += 2
        reasons.append(f"RSI oversold ({r:.0f})")
    elif r > 65:
        score -= 2
        reasons.append(f"RSI overbought ({r:.0f})")
    if last > e20 > e50:
        score += 2
        reasons.append("Price above EMA 20 above EMA 50 (uptrend)")
    elif last < e20 < e50:
        score -= 2
        reasons.append("Price below EMA 20 below EMA 50 (downtrend)")
    if vol_ratio > 1.5:
        reasons.append(f"Volume {vol_ratio:.1f}x the 20-day average")
        score += 1 if score > 0 else -1 if score < 0 else 0
    signal = "bullish_setup" if score >= 3 else "bearish_setup" if score <= -3 else "neutral"
    return {
        "symbol": sym, "price": round(last, 4), "change_pct": round((last / float(c.iloc[-2]) - 1) * 100, 3),
        "rsi": round(r, 1), "ema20": round(e20, 4), "ema50": round(e50, 4), "volume_ratio": round(vol_ratio, 2),
        "score": score, "signal": signal, "reasons": reasons,
    }


def technical_scan(symbols: list[str]) -> dict:
    data = md.histories(symbols, period="1y")
    rows = [r for s in symbols if (r := _technical_row(s.upper(), data.get(s.upper()))) is not None]
    rows.sort(key=lambda r: abs(r["score"]), reverse=True)
    return {
        "rows": rows,
        "method": "RSI(14) below 35 / above 65 scores +/-2; price vs EMA(20) and EMA(50) alignment scores +/-2; volume above 1.5x average adds conviction. |score| >= 3 is a setup.",
        "disclaimer": "Statistical setups only, not buy or sell recommendations.",
    }


def _options_anomaly(sym: str) -> dict | None:
    """Put/call volume ratio and single-contract volume spikes on the nearest expiry (yfinance, cached)."""

    def run():
        import yfinance as yf

        try:
            t = yf.Ticker(sym)
            exps = t.options
            if not exps:
                return None
            ch = t.option_chain(exps[0])
        except Exception:
            return None
        calls = ch.calls["volume"].fillna(0)
        puts = ch.puts["volume"].fillna(0)
        cv, pv = float(calls.sum()), float(puts.sum())
        allv = pd.concat([calls, puts])
        if cv + pv < 500:
            return None
        mx, avg = float(allv.max()), float(allv.mean() or 1)
        pcr = pv / cv if cv else None
        return {"expiry": exps[0], "call_volume": int(cv), "put_volume": int(pv), "put_call_ratio": None if pcr is None else round(pcr, 2), "max_contract_ratio": round(mx / avg, 1)}

    return md.cached(f"opts:{sym}", 1800, run)


def _alerts_for(sym: str, df: pd.DataFrame, neural: dict | None, with_options: bool) -> list[dict]:
    out: list[dict] = []
    if df is None or len(df) < 30:
        return out
    c, v = df["Close"], df["Volume"]
    last, prev = float(c.iloc[-1]), float(c.iloc[-2])
    move = (last / prev - 1) * 100
    vol_ratio = float(v.iloc[-1] / v.iloc[-21:-1].mean()) if v.iloc[-21:-1].mean() else 1.0
    year = df.tail(252)
    hi, lo = float(year["High"].max()), float(year["Low"].min())
    r = float(ind.rsi(c).iloc[-1])
    date = df.index[-1].strftime("%Y-%m-%d")

    def add(kind, severity, title, detail, data):
        out.append({"id": hashlib.md5(f"{sym}:{kind}:{date}".encode()).hexdigest()[:12], "symbol": sym, "type": kind, "severity": severity,
                    "title": title, "detail": detail, "data": data, "date": date})

    if vol_ratio >= 2.0:
        add("volume_spike", "high" if vol_ratio >= 3.5 else "medium", f"{sym} volume {vol_ratio:.1f}x average",
            f"Volume is {vol_ratio:.1f} times its 20-day average while price moved {move:+.1f}%. Heavy volume often accompanies news or institutional repositioning.",
            {"volume_ratio": round(vol_ratio, 2), "move_pct": round(move, 2)})
    if last >= hi * 0.99:
        add("breakout", "high", f"{sym} at a 52-week high", f"Close {last:.2f} is within 1% of the 52-week high {hi:.2f}. Breakouts on rising volume tend to be more durable.", {"close": last, "high_52w": hi})
    elif last <= lo * 1.01:
        add("breakdown", "high", f"{sym} at a 52-week low", f"Close {last:.2f} is within 1% of the 52-week low {lo:.2f}.", {"close": last, "low_52w": lo})
    if abs(move) >= 4:
        add("large_move", "high" if abs(move) >= 7 else "medium", f"{sym} {'up' if move > 0 else 'down'} {abs(move):.1f}% today",
            f"A {abs(move):.1f}% daily move is large relative to typical volatility for most large caps.", {"move_pct": round(move, 2)})
    if r <= 25 or r >= 75:
        add("rsi_extreme", "low", f"{sym} RSI {r:.0f}", f"RSI(14) at {r:.0f} is {'deeply oversold' if r <= 25 else 'strongly overbought'}; extremes can persist in strong trends.", {"rsi": round(r, 1)})
    if neural and neural.get("calibrated"):
        dec = neural["calibrated"]["decile"]
        if dec in (1, 10):
            add("neural_extreme", "medium", f"{sym} in the {'top' if dec == 10 else 'bottom'} model decile",
                f"Neural ensemble P(up, 5d) {neural['prob_up']:.2f}. Historically this decile rose {neural['calibrated']['historical_up_frequency'] * 100:.0f}% of the time (base rate {neural['calibrated']['base_rate'] * 100:.0f}%).",
                {"prob_up": neural["prob_up"], "decile": dec})
    if with_options:
        o = _options_anomaly(sym)
        if o and ((o["put_call_ratio"] is not None and (o["put_call_ratio"] >= 1.5 or o["put_call_ratio"] <= 0.4)) or o["max_contract_ratio"] >= 15):
            tilt = "put-heavy" if (o["put_call_ratio"] or 1) >= 1.5 else "call-heavy" if (o["put_call_ratio"] or 1) <= 0.4 else "concentrated"
            add("options_anomaly", "medium", f"{sym} options flow {tilt}",
                f"Nearest expiry {o['expiry']}: put/call volume {o['put_call_ratio']}, largest contract {o['max_contract_ratio']}x the average contract volume.", o)
    return out


def alerts(symbols: list[str], with_options: bool = True) -> dict:
    syms = [md.normalize_symbol(s) for s in symbols][:30]
    data = md.histories(syms, period="1y")
    neural: dict[str, dict] = {}
    try:
        from backend.dl import global_model

        for row in global_model.scan(syms, mc_samples=0)["rows"]:
            neural[row["symbol"]] = row
    except Exception:
        pass
    opt_syms = set(syms[:8]) if with_options else set()
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda s: _alerts_for(s, data.get(s), neural.get(s), s in opt_syms), syms))
    items = [a for r in results for a in r]
    items.sort(key=lambda a: (SEVERITY_RANK[a["severity"]], a["symbol"]))
    return {"alerts": items, "symbols": syms, "as_of": max((a["date"] for a in items), default=None)}


def heatmap(symbols: dict[str, tuple[str, str]]) -> dict:
    q = md.quotes(list(symbols))
    neural: dict[str, dict] = {}
    try:
        from backend.dl import global_model

        neural = {r["symbol"]: r for r in global_model.scan(list(symbols), mc_samples=0)["rows"]}
    except Exception:
        pass
    groups: dict[str, list] = {}
    for s, (name, sector) in symbols.items():
        if s not in q:
            continue
        n = neural.get(s)
        groups.setdefault(sector, []).append({"symbol": s, "name": name, "price": q[s]["price"], "change_pct": q[s]["change_pct"],
                                              "prob_up": n["prob_up"] if n else None, "signal": n["signal"] if n else None})
    out = []
    for sector, rows in groups.items():
        ch = [r["change_pct"] for r in rows if r["change_pct"] is not None]
        pu = [r["prob_up"] for r in rows if r["prob_up"] is not None]
        out.append({"sector": sector, "avg_change_pct": round(float(np.mean(ch)), 3) if ch else None,
                    "avg_prob_up": round(float(np.mean(pu)), 4) if pu else None,
                    "items": sorted(rows, key=lambda r: r["change_pct"] or 0, reverse=True)})
    out.sort(key=lambda g: g["avg_change_pct"] or 0, reverse=True)
    return {"groups": out}
