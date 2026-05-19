from fastapi import APIRouter, Depends
from pydantic import BaseModel

from apps.api.middleware.auth import get_current_user

router = APIRouter()


class WatchlistRequest(BaseModel):
    name: str
    tickers: list[str]


@router.post("/", status_code=201)
async def create_watchlist(payload: WatchlistRequest, user=Depends(get_current_user)):
    from apps.api.database import AsyncSessionLocal
    from database.models.users import Watchlist
    async with AsyncSessionLocal() as db:
        wl = Watchlist(
            user_id=user.user_id,
            name=payload.name,
            tickers=[t.upper() for t in payload.tickers],
        )
        db.add(wl)
        await db.commit()
        await db.refresh(wl)
    return {"watchlist_id": str(wl.watchlist_id)}


@router.get("/")
async def list_watchlists(user=Depends(get_current_user)):
    from apps.api.database import AsyncSessionLocal
    from database.models.users import Watchlist
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Watchlist).where(Watchlist.user_id == user.user_id)
        )
        wls = result.scalars().all()
    return [{"id": str(w.watchlist_id), "name": w.name, "tickers": w.tickers} for w in wls]


@router.get("/{watchlist_id}/intelligence")
async def get_watchlist_intelligence(watchlist_id: str, user=Depends(get_current_user)):
    """AI-narrated status of every ticker in a watchlist."""
    from intelligence.watchlist_intelligence.anomaly_detector import scan_watchlist
    return await scan_watchlist(watchlist_id, str(user.user_id))


@router.delete("/{watchlist_id}", status_code=204)
async def delete_watchlist(watchlist_id: str, user=Depends(get_current_user)):
    from apps.api.database import AsyncSessionLocal
    from database.models.users import Watchlist
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Watchlist).where(
                Watchlist.watchlist_id == watchlist_id,
                Watchlist.user_id == user.user_id,
            )
        )
        wl = result.scalar_one_or_none()
        if wl:
            await db.delete(wl)
            await db.commit()


@router.post("/{watchlist_id}/add-ticker")
async def add_ticker_to_watchlist(watchlist_id: str, ticker: str, user=Depends(get_current_user)):
    """Add a single ticker to an existing watchlist."""
    from apps.api.database import AsyncSessionLocal
    from database.models.users import Watchlist
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Watchlist).where(
                Watchlist.watchlist_id == watchlist_id,
                Watchlist.user_id == user.user_id,
            )
        )
        wl = result.scalar_one_or_none()
        if wl:
            tickers = list(wl.tickers or [])
            if ticker.upper() not in tickers:
                tickers.append(ticker.upper())
                wl.tickers = tickers
            await db.commit()
    return {"status": "ok"}


@router.get("/alerts/signals")
async def get_buy_sell_signals(user=Depends(get_current_user)):
    """
    Generate buy/sell signal suggestions for all watchlisted tickers.
    Based on technical analysis — NOT financial advice.
    """
    from apps.api.database import AsyncSessionLocal
    from database.models.users import Watchlist
    from sqlalchemy import select
    import yfinance as yf
    import pandas as pd

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Watchlist).where(Watchlist.user_id == user.user_id)
        )
        watchlists = result.scalars().all()

    all_tickers: set[str] = set()
    for wl in watchlists:
        for t in (wl.tickers or []):
            all_tickers.add(t)

    signals = []
    for ticker in all_tickers:
        try:
            hist = yf.Ticker(ticker).history(period="3mo", interval="1d")
            if hist.empty or len(hist) < 20:
                continue
            close = hist["Close"]
            volume = hist["Volume"]

            # RSI
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rsi = (100 - 100 / (1 + gain / loss)).iloc[-1]

            # EMAs
            ema20 = close.ewm(span=20).mean().iloc[-1]
            ema50 = close.ewm(span=50).mean().iloc[-1]
            current = close.iloc[-1]

            # Volume ratio
            vol_ratio = volume.iloc[-1] / volume.rolling(20).mean().iloc[-1]

            # Signal logic
            signal = "neutral"
            reason = []
            score = 0

            if rsi < 35:
                score += 2; reason.append(f"RSI oversold ({rsi:.0f})")
            elif rsi > 65:
                score -= 2; reason.append(f"RSI overbought ({rsi:.0f})")

            if current > ema20 > ema50:
                score += 2; reason.append("Price above both EMAs — uptrend")
            elif current < ema20 < ema50:
                score -= 2; reason.append("Price below both EMAs — downtrend")

            if vol_ratio > 1.5:
                reason.append(f"Volume {vol_ratio:.1f}× average — confirmation")

            if score >= 3:
                signal = "bullish_setup"
            elif score <= -3:
                signal = "bearish_setup"

            signals.append({
                "ticker": ticker,
                "signal": signal,
                "score": score,
                "current_price": round(float(current), 2),
                "rsi": round(float(rsi), 1),
                "reasons": reason,
                "disclaimer": "Statistical signal only — not a buy/sell recommendation.",
            })
        except Exception:
            pass

    signals.sort(key=lambda x: abs(x["score"]), reverse=True)
    return {
        "signals": signals,
        "disclaimer": "These signals are for educational purposes only and do not constitute financial advice. Always conduct your own research.",
    }
