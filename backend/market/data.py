"""
Market data access (Yahoo Finance via yfinance).

- Batch downloads (one request for many symbols) instead of per-symbol loops.
- In-process TTL cache: warm serverless instances reuse recent results.
- Adjusted prices (dividends/splits), timezone-naive daily index.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable

import numpy as np
import pandas as pd

OHLCV = ["Open", "High", "Low", "Close", "Volume"]


class MarketDataError(RuntimeError):
    pass


_cache: dict[str, tuple[float, Any]] = {}
_lock = threading.Lock()


def cached(key: str, ttl: float | Callable[[Any], float], fn: Callable[[], Any], keep: Callable[[Any], bool] = bool) -> Any:
    """Memoise fn(). Results rejected by `keep` (empty by default) are not stored, so a failed upstream call is retried."""
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and hit[0] > now:
            return hit[1]
    value = fn()
    if not keep(value):
        return value
    seconds = ttl(value) if callable(ttl) else ttl
    with _lock:
        _cache[key] = (now + seconds, value)
        if len(_cache) > 512:  # crude bound on memory
            for k in sorted(_cache, key=lambda k: _cache[k][0])[:128]:
                _cache.pop(k, None)
    return value


def _ttl_for(interval: str) -> float:
    return 60.0 if interval in ("1m", "2m", "5m", "15m", "30m", "60m", "1h") else 300.0


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=OHLCV)
    df = df[[c for c in OHLCV if c in df.columns]].copy()
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    df.index = idx
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df.dropna(subset=["Close"])
    df["Volume"] = df["Volume"].fillna(0)
    return df.astype(float)


def _download(symbols: list[str], period: str, interval: str) -> dict[str, pd.DataFrame]:
    import yfinance as yf

    try:
        raw = yf.download(
            symbols, period=period, interval=interval, group_by="ticker", auto_adjust=True,
            threads=True, progress=False, timeout=20, multi_level_index=True,
        )
    except Exception as exc:  # network / Yahoo errors
        raise MarketDataError(f"market data request failed: {exc}") from exc
    out: dict[str, pd.DataFrame] = {}
    if raw is None or raw.empty:
        return out
    if isinstance(raw.columns, pd.MultiIndex):
        level0 = set(raw.columns.get_level_values(0))
        for s in symbols:
            if s in level0:
                df = _clean(raw[s])
                if not df.empty:
                    out[s] = df
    elif len(symbols) == 1:
        df = _clean(raw)
        if not df.empty:
            out[symbols[0]] = df
    return out


def normalize_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    if not s or len(s) > 15 or not all(c.isalnum() or c in ".-^=" for c in s):
        raise MarketDataError(f"invalid symbol {symbol!r}")
    return s


def valid_symbols(symbols: list[str]) -> list[str]:
    """Normalised, de-duplicated symbols with malformed entries dropped, so one typo cannot fail a whole list."""
    out: list[str] = []
    for s in symbols:
        try:
            n = normalize_symbol(s)
        except MarketDataError:
            continue
        if n not in out:
            out.append(n)
    return out


def histories(symbols: list[str], period: str = "1y", interval: str = "1d", ttl: float | None = None) -> dict[str, pd.DataFrame]:
    """OHLCV for many symbols with a single batched request (cached per symbol set)."""
    syms = sorted(valid_symbols(symbols))
    if not syms:
        return {}
    key = f"hist:{','.join(syms)}:{period}:{interval}"
    full = ttl if ttl is not None else _ttl_for(interval)
    # A partial answer usually means Yahoo throttled some symbols, so keep it only briefly
    return cached(key, lambda v: full if len(v) == len(syms) else min(full, 20.0), lambda: _download(syms, period, interval))


def history(symbol: str, period: str = "5y", interval: str = "1d") -> pd.DataFrame:
    sym = normalize_symbol(symbol)
    df = histories([sym], period, interval).get(sym)
    if df is None or df.empty:
        raise MarketDataError(f"no price data for {sym}")
    return df


def quotes(symbols: list[str]) -> dict[str, dict]:
    """Latest price and day change from daily bars (today's bar updates intraday)."""
    data = histories(symbols, period="1mo", interval="1d", ttl=30.0)
    out = {}
    for sym, df in data.items():
        if len(df) < 2:
            continue
        last, prev = df.iloc[-1], df.iloc[-2]
        price, prev_close = float(last["Close"]), float(prev["Close"])
        out[sym] = {
            "symbol": sym,
            "price": round(price, 4),
            "prev_close": round(prev_close, 4),
            "change": round(price - prev_close, 4),
            "change_pct": round((price / prev_close - 1.0) * 100.0, 3) if prev_close else None,
            "volume": int(last["Volume"]),
            "avg_volume_20d": int(df["Volume"].tail(20).mean()),
            "as_of": df.index[-1].strftime("%Y-%m-%d"),
            "spark": [round(float(v), 4) for v in df["Close"].tail(22)],
        }
    return out


def search(query: str, limit: int = 8) -> list[dict]:
    q = query.strip()
    if not q:
        return []

    def run():
        import yfinance as yf

        try:
            res = yf.Search(q, max_results=limit, news_count=0, enable_fuzzy_query=True)
            items = res.quotes or []
        except Exception:
            return []
        return [
            {
                "symbol": it.get("symbol"),
                "name": it.get("shortname") or it.get("longname") or it.get("symbol"),
                "exchange": it.get("exchDisp") or it.get("exchange"),
                "type": it.get("quoteType"),
            }
            for it in items
            if it.get("symbol") and it.get("quoteType") in ("EQUITY", "ETF", "INDEX", "CRYPTOCURRENCY", "MUTUALFUND", "FUTURE", "CURRENCY")
        ]

    return cached(f"search:{q.lower()}:{limit}", 3600, run)


def profile(symbol: str) -> dict:
    """Name / sector / industry / market cap (slow endpoint, cached for a day)."""
    sym = normalize_symbol(symbol)

    def run():
        import yfinance as yf

        try:
            info = yf.Ticker(sym).get_info() or {}
        except Exception:
            info = {}
        high, low = info.get("fiftyTwoWeekHigh"), info.get("fiftyTwoWeekLow")
        if not (high and low and high > 0 and low > 0):  # Yahoo reports a 52-week low of 0 for some yield indices
            try:
                year = history(sym, "1y")
                high, low = float(year["High"].max()), float(year["Low"].min())
            except MarketDataError:
                high, low = None, None
        return {
            "symbol": sym,
            "name": info.get("longName") or info.get("shortName") or sym,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
            "currency": info.get("currency"),
            "exchange": info.get("fullExchangeName") or info.get("exchange"),
            "summary": (info.get("longBusinessSummary") or "")[:600] or None,
            "pe": info.get("trailingPE"),
            "beta": info.get("beta"),
            "high_52w": high,
            "low_52w": low,
        }

    return cached(f"profile:{sym}", 86400, run, keep=lambda v: v.get("name") != sym or bool(v.get("sector")))


def news(symbol: str, limit: int = 10) -> list[dict]:
    """Recent headlines from Yahoo Finance (no API key needed). Handles old and new payload shapes."""
    sym = normalize_symbol(symbol)

    def run():
        import yfinance as yf

        try:
            items = yf.Ticker(sym).get_news(count=limit) or []
        except Exception:
            return []
        out = []
        for it in items:
            c = it.get("content") or it
            url = (c.get("canonicalUrl") or {}).get("url") or (c.get("clickThroughUrl") or {}).get("url") or c.get("link")
            ts = c.get("pubDate") or c.get("displayTime")
            if not ts and c.get("providerPublishTime"):
                ts = pd.Timestamp(c["providerPublishTime"], unit="s").isoformat()
            title = c.get("title")
            if not title:
                continue
            out.append({
                "title": title,
                "summary": (c.get("summary") or c.get("description") or "")[:400] or None,
                "source": (c.get("provider") or {}).get("displayName") or c.get("publisher"),
                "published_at": ts,
                "url": url,
            })
        return out[:limit]

    return cached(f"news:{sym}:{limit}", 900, run)


def to_float_list(a, digits: int = 6) -> list:
    arr = np.asarray(a, dtype=float)
    return [None if not np.isfinite(v) else round(float(v), digits) for v in arr]
