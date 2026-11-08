"""Market snapshot: macro instruments, sector ETFs, movers and a rule-based regime label."""
from __future__ import annotations

import numpy as np

from backend.market import data as md
from backend.market import indicators as ind

MACRO = {
    "SPY": "S&P 500", "QQQ": "Nasdaq 100", "IWM": "Russell 2000", "DIA": "Dow 30",
    "^VIX": "VIX", "^TNX": "US 10Y yield", "DX-Y.NYB": "US dollar", "GC=F": "Gold", "CL=F": "Crude oil", "BTC-USD": "Bitcoin",
}
SECTORS = {
    "XLK": "Technology", "XLC": "Communication", "XLY": "Consumer Disc.", "XLF": "Financials", "XLV": "Health Care",
    "XLI": "Industrials", "XLE": "Energy", "XLB": "Materials", "XLP": "Consumer Staples", "XLU": "Utilities", "XLRE": "Real Estate",
}
MOVERS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO", "AMD", "NFLX", "ORCL", "CRM", "ADBE", "INTC",
    "JPM", "BAC", "GS", "V", "MA", "XOM", "CVX", "LLY", "UNH", "JNJ", "PFE", "WMT", "COST", "HD", "KO", "PG", "DIS", "BA", "CAT", "GE",
]


def regime() -> dict:
    """Transparent rule-based regime from SPY trend/momentum and VIX level (context for the models)."""
    data = md.histories(["SPY", "^VIX"], period="2y")
    spy, vix = data.get("SPY"), data.get("^VIX")
    if spy is None or len(spy) < 210:
        return {"label": "unknown", "description": "Not enough data."}
    c = spy["Close"]
    sma200 = float(ind.sma(c, 200).iloc[-1])
    ret20 = float(c.iloc[-1] / c.iloc[-21] - 1)
    vol20 = float(np.log(c).diff().tail(20).std() * np.sqrt(252))
    vix_now = float(vix["Close"].iloc[-1]) if vix is not None and len(vix) else None
    above = float(c.iloc[-1]) > sma200
    if vix_now is not None and vix_now >= 30:
        label, desc = "high_volatility", "VIX at or above 30: stress regime, wide daily ranges, correlations rise."
    elif above and ret20 > 0.03:
        label, desc = "bull_trending", "S&P 500 above its 200-day average with strong 1-month momentum."
    elif above and abs(ret20) <= 0.03:
        label, desc = "bull_consolidating", "S&P 500 above its 200-day average, momentum flat: consolidation."
    elif above:
        label, desc = "bull_pullback", "S&P 500 above its 200-day average but pulling back over the past month."
    elif ret20 < -0.03:
        label, desc = "bear_trending", "S&P 500 below its 200-day average with negative 1-month momentum."
    else:
        label, desc = "bear_ranging", "S&P 500 below its 200-day average, momentum mixed."
    return {
        "label": label,
        "description": desc,
        "spy_vs_sma200": round(float(c.iloc[-1]) / sma200 - 1, 4),
        "spy_return_20d": round(ret20, 4),
        "spy_realized_vol_20d": round(vol20, 4),
        "vix": None if vix_now is None else round(vix_now, 2),
    }


def snapshot() -> dict:
    syms = list(MACRO) + list(SECTORS) + MOVERS
    q = md.quotes(syms)
    macro = [{**q[s], "label": MACRO[s]} for s in MACRO if s in q]
    sectors = sorted(
        [{**q[s], "label": SECTORS[s]} for s in SECTORS if s in q],
        key=lambda r: r["change_pct"] if r["change_pct"] is not None else 0, reverse=True,
    )
    movers = sorted([q[s] for s in MOVERS if s in q and q[s]["change_pct"] is not None], key=lambda r: r["change_pct"], reverse=True)
    for m in movers:
        m["volume_ratio"] = round(m["volume"] / m["avg_volume_20d"], 2) if m["avg_volume_20d"] else None
    adv = sum(1 for m in movers if m["change_pct"] > 0)
    # The equity session date: crypto and futures also print on weekends
    as_of = (q.get("SPY") or {}).get("as_of") or max((r["as_of"] for r in q.values()), default=None)
    return {
        "as_of": as_of,
        "macro": macro,
        "sectors": sectors,
        "gainers": [m for m in movers if m["change_pct"] > 0][:6],
        "losers": [m for m in movers[::-1] if m["change_pct"] < 0][:6],
        "breadth": {"advancing": adv, "declining": len(movers) - adv, "universe": len(movers)},
    }
