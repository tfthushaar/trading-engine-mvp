"""
Real-time watchlist monitor.
Scans all user watchlists for anomalies and publishes alerts via event bus.
"""
import asyncio
import json
from datetime import datetime

import yfinance as yf
import pandas as pd

from pipeline.event_bus import event_bus, MarketEvent


VOLUME_SPIKE_THRESHOLD = 2.5   # current vol / 20d avg vol
PRICE_MOVE_THRESHOLD = 0.03    # 3% intraday move = alert


async def check_ticker(ticker: str) -> list[dict]:
    """Run all anomaly checks on a single ticker. Returns list of alert dicts."""
    alerts = []
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="25d", interval="1d")
        if hist.empty:
            return alerts

        info = t.fast_info
        current_price = info.last_price
        prev_close = info.previous_close
        current_vol = info.three_month_average_volume  # approximate

        # Volume spike
        avg_vol_20d = hist["Volume"].rolling(20).mean().iloc[-1]
        today_vol = hist["Volume"].iloc[-1]
        vol_ratio = today_vol / avg_vol_20d if avg_vol_20d > 0 else 1.0

        if vol_ratio >= VOLUME_SPIKE_THRESHOLD:
            alerts.append({
                "type": "volume_spike",
                "ticker": ticker,
                "vol_ratio": round(vol_ratio, 2),
                "message": f"{ticker} volume is {vol_ratio:.1f}× the 20-day average.",
            })

        # Price move
        if prev_close:
            move_pct = (current_price - prev_close) / prev_close
            if abs(move_pct) >= PRICE_MOVE_THRESHOLD:
                direction = "up" if move_pct > 0 else "down"
                alerts.append({
                    "type": "price_move",
                    "ticker": ticker,
                    "move_pct": round(move_pct * 100, 2),
                    "message": f"{ticker} is {direction} {abs(move_pct)*100:.1f}% today.",
                })

        # 52-week high breakout
        high_52w = hist["High"].max()
        if current_price >= high_52w * 0.99:
            alerts.append({
                "type": "breakout",
                "ticker": ticker,
                "message": f"{ticker} is approaching/breaking its 52-week high of ${high_52w:.2f}.",
            })

    except Exception as exc:
        print(f"[WatchlistMonitor] Error checking {ticker}: {exc}")

    return alerts


async def scan_all_watchlists():
    """Called by scheduler — scan all watchlisted tickers and publish alerts."""
    from apps.api.database import AsyncSessionLocal
    from database.models.users import Watchlist
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Watchlist))
        watchlists = result.scalars().all()

    # Collect unique tickers across all watchlists
    all_tickers: dict[str, list[str]] = {}  # ticker -> [user_id list]
    for wl in watchlists:
        for ticker in (wl.tickers or []):
            all_tickers.setdefault(ticker, []).append(str(wl.user_id))

    for ticker, user_ids in all_tickers.items():
        alerts = await check_ticker(ticker)
        for alert in alerts:
            event = MarketEvent(
                event_type=alert["type"],
                source="watchlist_monitor",
                ticker=ticker,
                payload={**alert, "user_ids": user_ids},
            )
            await event_bus.publish(event)

            # Push directly to each user's alert channel via Redis
            import redis.asyncio as aioredis
            from apps.api.config import get_settings
            settings = get_settings()
            r = aioredis.from_url(settings.redis_url, decode_responses=True)
            for uid in user_ids:
                await r.publish(f"alerts:{uid}", json.dumps({
                    "ticker": ticker,
                    "type": alert["type"],
                    "message": alert["message"],
                    "timestamp": datetime.utcnow().isoformat(),
                }))
            await r.aclose()
