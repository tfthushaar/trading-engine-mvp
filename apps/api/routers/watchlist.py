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
