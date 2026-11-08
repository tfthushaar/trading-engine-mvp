"""Market data endpoints: overview, quotes, charts with selectable timeframes, search, profile, technicals."""
from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Query
from starlette.concurrency import run_in_threadpool

from backend.http import ok
from backend.market import data as md
from backend.market import indicators as ind
from backend.market import overview

router = APIRouter(prefix="/api/market", tags=["market"])

# Range presets (TradingView style) -> Yahoo period + default bar size
RANGES: dict[str, dict] = {
    "1d": {"period": "1d", "interval": "5m"},
    "5d": {"period": "5d", "interval": "15m"},
    "1mo": {"period": "1mo", "interval": "1h"},
    "3mo": {"period": "3mo", "interval": "1d"},
    "6mo": {"period": "6mo", "interval": "1d"},
    "ytd": {"period": "ytd", "interval": "1d"},
    "1y": {"period": "1y", "interval": "1d"},
    "2y": {"period": "2y", "interval": "1d"},
    "5y": {"period": "5y", "interval": "1wk"},
    "10y": {"period": "10y", "interval": "1wk"},
    "max": {"period": "max", "interval": "1mo"},
}
# Longest range Yahoo serves for each bar size
INTERVAL_MAX_RANGE = {
    "1m": ["1d", "5d"],
    "5m": ["1d", "5d", "1mo"],
    "15m": ["1d", "5d", "1mo"],
    "30m": ["1d", "5d", "1mo"],
    "1h": ["1d", "5d", "1mo", "3mo", "6mo", "ytd", "1y", "2y"],
    "4h": ["5d", "1mo", "3mo", "6mo", "ytd", "1y", "2y"],
    "1d": list(RANGES),
    "1wk": [r for r in RANGES if r not in ("1d", "5d")],
    "1mo": [r for r in RANGES if r not in ("1d", "5d", "1mo", "3mo")],
}


def timeframes() -> dict:
    return {"ranges": RANGES, "intervals": INTERVAL_MAX_RANGE}


def _chart(symbol: str, rng: str, interval: str | None) -> dict:
    if rng not in RANGES:
        raise ValueError(f"range must be one of {', '.join(RANGES)}")
    iv = interval or RANGES[rng]["interval"]
    if iv not in INTERVAL_MAX_RANGE:
        raise ValueError(f"interval must be one of {', '.join(INTERVAL_MAX_RANGE)}")
    if rng not in INTERVAL_MAX_RANGE[iv]:
        raise ValueError(f"{iv} bars are not available for the {rng} range")
    fetch_iv = "1h" if iv == "4h" else iv
    df = md.history(symbol, period=RANGES[rng]["period"], interval=fetch_iv)
    if iv == "4h":
        df = df.resample("4h", origin="start_day", offset="9h30min").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}).dropna(subset=["Close"])
    df = df.tail(5000)
    intraday = iv not in ("1d", "1wk", "1mo")
    # Epoch seconds of the exchange-local wall time (independent of pandas' datetime resolution)
    ts = ((df.index - pd.Timestamp("1970-01-01")) // pd.Timedelta(seconds=1)).tolist()
    bars = [
        {"t": int(t), "o": round(float(o), 4), "h": round(float(h), 4), "l": round(float(lo), 4), "c": round(float(c), 4), "v": int(v)}
        for t, o, h, lo, c, v in zip(ts, df["Open"], df["High"], df["Low"], df["Close"], df["Volume"])
    ]
    first, last = float(df["Close"].iloc[0]), float(df["Close"].iloc[-1])
    return {
        "symbol": md.normalize_symbol(symbol),
        "range": rng,
        "interval": iv,
        "intraday": intraday,
        "bars": bars,
        "first_close": first,
        "last_close": last,
        "change_pct": round((last / first - 1) * 100, 3) if first else None,
        "high": float(df["High"].max()),
        "low": float(df["Low"].min()),
        "as_of": df.index[-1].isoformat(),
        "timezone_note": "Intraday times are exchange local time.",
    }


@router.get("/overview")
async def market_overview():
    snap = await run_in_threadpool(overview.snapshot)
    reg = await run_in_threadpool(overview.regime)
    return ok({**snap, "regime": reg}, cache_s=60)


@router.get("/quotes")
async def quotes(symbols: str = Query(..., description="Comma-separated symbols")):
    syms = [s for s in symbols.split(",") if s.strip()][:60]
    return ok(await run_in_threadpool(md.quotes, syms), cache_s=30)


@router.get("/chart/{symbol}")
async def chart(symbol: str, range: str = Query("6mo"), interval: str | None = Query(None)):  # noqa: A002
    data = await run_in_threadpool(_chart, symbol, range, interval)
    return ok(data, cache_s=30 if data["intraday"] else 300)


@router.get("/timeframes")
async def get_timeframes():
    return ok(timeframes(), cache_s=86400)


@router.get("/search")
async def search(q: str = Query(..., min_length=1, max_length=40)):
    return ok(await run_in_threadpool(md.search, q), cache_s=3600)


@router.get("/profile/{symbol}")
async def profile(symbol: str):
    return ok(await run_in_threadpool(md.profile, symbol), cache_s=3600)


@router.get("/technicals/{symbol}")
async def technicals(symbol: str):
    df = await run_in_threadpool(md.history, symbol, "2y", "1d")
    snap = ind.snapshot(df)
    snap["symbol"] = md.normalize_symbol(symbol)
    snap["as_of"] = pd.Timestamp(df.index[-1]).strftime("%Y-%m-%d")
    return ok(snap, cache_s=120)
