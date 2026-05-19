from fastapi import APIRouter, Query, Depends
from pydantic import BaseModel
from typing import Optional
import yfinance as yf
import pandas as pd

from apps.api.middleware.auth import get_current_user

router = APIRouter()


class PriceBar(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


@router.get("/quote/{ticker}")
async def get_quote(ticker: str):
    """Live quote for a single ticker."""
    t = yf.Ticker(ticker.upper())
    info = t.fast_info
    return {
        "ticker": ticker.upper(),
        "price": info.last_price,
        "change": info.last_price - info.previous_close,
        "change_pct": round((info.last_price - info.previous_close) / info.previous_close * 100, 2),
        "volume": info.three_month_average_volume,
        "market_cap": info.market_cap,
    }


@router.get("/history/{ticker}", response_model=list[PriceBar])
async def get_history(
    ticker: str,
    period: str = Query("6mo", description="1d 5d 1mo 3mo 6mo 1y 2y 5y"),
    interval: str = Query("1d", description="1m 5m 15m 1h 1d 1wk"),
):
    """OHLCV history for charts."""
    t = yf.Ticker(ticker.upper())
    df = t.history(period=period, interval=interval)
    df = df.reset_index()
    return [
        PriceBar(
            date=str(row["Date"])[:10] if "Date" in df.columns else str(row["Datetime"])[:16],
            open=round(row["Open"], 4),
            high=round(row["High"], 4),
            low=round(row["Low"], 4),
            close=round(row["Close"], 4),
            volume=int(row["Volume"]),
        )
        for _, row in df.iterrows()
    ]


@router.get("/sector-heatmap")
async def get_sector_heatmap():
    """Sector ETF performance snapshot."""
    sector_etfs = {
        "Technology": "XLK", "Financials": "XLF", "Healthcare": "XLV",
        "Energy": "XLE", "Consumer Disc.": "XLY", "Industrials": "XLI",
        "Utilities": "XLU", "Materials": "XLB", "Real Estate": "XLRE",
        "Consumer Staples": "XLP", "Communication": "XLC",
    }
    results = []
    for sector, etf in sector_etfs.items():
        try:
            t = yf.Ticker(etf)
            info = t.fast_info
            change_pct = round(
                (info.last_price - info.previous_close) / info.previous_close * 100, 2
            )
            results.append({"sector": sector, "etf": etf, "change_pct": change_pct})
        except Exception:
            results.append({"sector": sector, "etf": etf, "change_pct": 0.0})
    return results


@router.get("/movers")
async def get_movers():
    """Top gainers and losers from major indices."""
    symbols = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AMD", "NFLX", "INTC"]
    results = []
    for sym in symbols:
        try:
            t = yf.Ticker(sym)
            info = t.fast_info
            change_pct = round(
                (info.last_price - info.previous_close) / info.previous_close * 100, 2
            )
            results.append({"ticker": sym, "price": info.last_price, "change_pct": change_pct})
        except Exception:
            pass
    results.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    return {"gainers": [r for r in results if r["change_pct"] > 0][:5],
            "losers": [r for r in results if r["change_pct"] < 0][:5]}


@router.get("/macro")
async def get_macro_snapshot():
    """Key macro instruments snapshot."""
    instruments = {"SPY": "S&P 500", "QQQ": "NASDAQ", "IWM": "Russell 2000",
                   "^VIX": "VIX", "DX-Y.NYB": "DXY", "^TNX": "10Y Yield"}
    results = {}
    for sym, label in instruments.items():
        try:
            t = yf.Ticker(sym)
            info = t.fast_info
            results[label] = {
                "symbol": sym,
                "price": round(info.last_price, 2),
                "change_pct": round(
                    (info.last_price - info.previous_close) / info.previous_close * 100, 2
                ),
            }
        except Exception:
            results[label] = {"symbol": sym, "price": None, "change_pct": None}
    return results
